import asyncio
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.core import config
from app.core.config import apply_glossary_corrections
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessCorrectionResponse,
    SubtitleCorrectionItem,
    HarnessInstructionRequest,
    HarnessPlanResponse
)
from app.harness_bridge.embedded import EmbeddedHarnessBridge
from app.harness_bridge.prompting import build_correction_prompt
from app.harness_bridge import llm_client

class CodexHarnessBridge(BaseHarnessBridge):
    """
    面向 Codex CLI (codex exec) 的生产级外部子进程桥接器。
    具备 Windows 管道防挂起、临时文件消息提取、结构化 JSON 解析与智能降级能力。
    """
    def __init__(self):
        self._fallback = EmbeddedHarnessBridge()

    async def is_available(self) -> bool:
        return bool(shutil.which("codex"))

    def _extract_json(self, raw: str) -> Any:
        """从模型输出提取干净的 JSON 数据结构"""
        raw = raw.strip()
        if not raw:
            raise ValueError("Codex CLI returned empty output")
        
        # 1. 尝试直接解析
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 2. 尝试正则提取 ```json ... ``` 块
        m = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # 3. 寻找最外层花括号或方括号
        fb, lb = raw.find("{"), raw.rfind("}")
        if fb != -1 and lb != -1 and lb > fb:
            try:
                return json.loads(raw[fb:lb + 1])
            except Exception:
                pass

        fb2, lb2 = raw.find("["), raw.rfind("]")
        if fb2 != -1 and lb2 != -1 and lb2 > fb2:
            try:
                return json.loads(raw[fb2:lb2 + 1])
            except Exception:
                pass

        raise ValueError(f"Failed to parse JSON payload from response: {raw[:200]}")

    async def _run_codex_cli(
        self,
        prompt: str,
        timeout: float = 35.0,
        model_override: Optional[str] = None
    ) -> Tuple[bool, str, float]:
        """
        执行大模型推理：
        1. 优先直连 codex 本地配置（~/.codex/config.toml 的本地代理/供应商，与设置页 API 配置完全隔离）。
        2. 直连不可用时回退至命令行 `codex exec`。
        """
        # 1. 共享直连传输层，但提供方强制绑定 codex 本地配置，不读设置页
        success, content, latency_ms = await llm_client.chat_completion(
            prompt, timeout=timeout, model_override=model_override,
            provider=llm_client.codex_provider()
        )
        if success:
            return True, content, latency_ms
        print(f"[CodexBridge] codex 本地配置直连未成功，回退 codex CLI: {content[:160]}")

        # 2. 回退到 Codex CLI 进程执行
        start_time = time.time()
        if not await self.is_available():
            return False, "codex CLI not found in system PATH", 0.0

        temp_fd, temp_file_path = tempfile.mkstemp(suffix=".txt", prefix="codex_out_")
        os.close(temp_fd)

        base_cmd = ["codex"]
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            js_path = Path(appdata) / "npm" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            if js_path.exists() and shutil.which("node"):
                base_cmd = ["node", str(js_path)]
            elif os.name == "nt":
                base_cmd = ["cmd.exe", "/c", "codex"]
        elif os.name == "nt":
            base_cmd = ["cmd.exe", "/c", "codex"]

        cmd = base_cmd + [
            "exec",
            "--sandbox", "read-only",
            "--ephemeral",
            "-o", temp_file_path
        ]

        if active_model:
            cmd.extend(["-m", active_model])

        cmd.append(prompt)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                latency_ms = (time.time() - start_time) * 1000
                return False, f"Codex CLI execution timed out after {timeout}s", latency_ms

            latency_ms = (time.time() - start_time) * 1000

            last_message = ""
            if os.path.exists(temp_file_path):
                try:
                    with open(temp_file_path, "r", encoding="utf-8", errors="replace") as f:
                        last_message = f.read().strip()
                except Exception:
                    last_message = ""

            if not last_message and stdout_bytes:
                last_message = stdout_bytes.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0 and not last_message:
                err_msg = stderr_bytes.decode("utf-8", errors="replace").strip()
                return False, f"Codex CLI exited with code {proc.returncode}: {err_msg}", latency_ms

            return True, last_message, latency_ms

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"Exception executing Codex CLI: {str(e)}", latency_ms
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

    async def stream_chat(self, prompt: str, model_override: Optional[str] = None):
        """
        全实时 Token 级流式输出：
        优先直连本机 Codex 后端代理的 /v1/responses 实时 SSE 流（产出 reasoning 思考链与 content 增量）；
        若代理未就绪，则优雅回退至 CLI 进程 JSONL 流。
        """
        import httpx
        provider_cfg = config.get_codex_provider_config()
        base_url = provider_cfg.get("base_url", "http://127.0.0.1:15721/v1").rstrip("/")
        token = provider_cfg.get("token", "PROXY_MANAGED")
        model = (model_override or provider_cfg.get("model") or config.LLM_MODEL or "glm-5.3-flash").strip()

        # 1. 优先尝试本地 Codex 代理的 /v1/responses 实时流式响应
        try:
            url = f"{base_url}/responses"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "model": model,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
                "stream": True
            }
            async with httpx.AsyncClient(trust_env=False) as client:
                async with client.stream("POST", url, json=payload, headers=headers, timeout=50.0) as resp:
                    if resp.status_code == 200:
                        async for line in resp.aiter_lines():
                            line_str = line.strip()
                            if not line_str or not line_str.startswith("data: "):
                                continue
                            try:
                                d = json.loads(line_str[6:])
                                evt_type = d.get("type")
                                # 实时思考推理过程
                                if evt_type == "response.reasoning_summary_text.delta":
                                    delta_txt = d.get("delta", "")
                                    if delta_txt:
                                        yield {"type": "reasoning", "delta": delta_txt}
                                # 实时文本输出
                                elif evt_type == "response.output_text.delta":
                                    delta_txt = d.get("delta", "")
                                    if delta_txt:
                                        yield {"type": "content", "delta": delta_txt}
                                elif evt_type == "response.completed":
                                    yield {"type": "done"}
                                    return
                            except Exception:
                                pass
                        yield {"type": "done"}
                        return
        except Exception:
            pass

        # 2. 备用方案：通过 Codex CLI 进程执行
        if not await self.is_available():
            yield {"type": "content", "delta": "本地未检测到可用的 Codex CLI 工具，正在启用内置离线助手回答...\n\n"}
            yield {"type": "content", "delta": f"已收到您的指令：{prompt}\n当前为离线模式。"}
            yield {"type": "done"}
            return

        base_cmd = ["codex"]
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            js_path = Path(appdata) / "npm" / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
            if js_path.exists() and shutil.which("node"):
                base_cmd = ["node", str(js_path)]
            elif os.name == "nt":
                base_cmd = ["cmd.exe", "/c", "codex"]
        elif os.name == "nt":
            base_cmd = ["cmd.exe", "/c", "codex"]

        cmd = base_cmd + [
            "exec",
            "--sandbox", "read-only",
            "--ephemeral",
            "--json"
        ]

        active_model = model or "glm-5.3-flash"
        if active_model:
            cmd.extend(["-m", active_model])

        cmd.append(prompt)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                txt = line.decode("utf-8", errors="replace").strip()
                if not txt:
                    continue
                try:
                    data = json.loads(txt)
                    evt_type = data.get("type")
                    if evt_type == "item.completed":
                        item = data.get("item", {})
                        item_type = item.get("type")
                        if item_type == "agent_message":
                            msg_text = item.get("text", "")
                            if msg_text:
                                yield {"type": "content", "delta": msg_text}
                        elif item_type == "reasoning":
                            reasoning_text = item.get("text", "")
                            if reasoning_text:
                                yield {"type": "reasoning", "delta": reasoning_text}
                except Exception:
                    pass

            await proc.wait()
            yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
            yield {"type": "done"}
        finally:
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass


    async def ping(self, model_override: Optional[str] = None) -> Tuple[bool, str, float, str]:
        """连通性与模型可用性探针"""
        if not await self.is_available():
            return False, "", 0.0, "未检测到本地已安装的 codex 命令行工具"

        prompt = 'Output only a single valid JSON object: {"status": "ok", "agent": "codex"}. No other text or markdown.'
        success, out, latency = await self._run_codex_cli(prompt, timeout=25.0, model_override=model_override)
        detected_model = model_override or config.LLM_MODEL or config.get_codex_configured_model() or "glm-5.3-flash"

        if success:
            try:
                data = self._extract_json(out)
                if data.get("status") == "ok":
                    return True, detected_model, latency, "Codex CLI 连通正常，探针响应成功"
                return True, detected_model, latency, f"Codex CLI 响应已接收: {out[:80]}"
            except Exception:
                return True, detected_model, latency, "Codex CLI 进程执行成功"

        # 若子进程超时，但 CLI 本身存在且可用
        if "timed out" in out.lower():
            return False, detected_model, latency, f"Codex CLI 探测响应超时 (>25s)，请检查上游代理或模型网络"

        return False, detected_model, latency, f"Codex CLI 调用异常: {out[:120]}"

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> HarnessCorrectionResponse:
        """
        利用 Codex CLI 对口播 ASR 字幕进行上下文与驾校专有词语义纠错。
        超时或异常时平滑降级至 EmbeddedHarnessBridge。
        """
        if not await self.is_available():
            fallback_res = await self._fallback.correct_subtitles(request)
            fallback_res.harness_engine_used = "codex (fallback embedded: cli not found)"
            return fallback_res

        # 1. 剔除无关信息，仅提取 id 与 text，精简 Token 负载
        clean_input = [
            {"id": s.get("id"), "text": s.get("raw_text") or s.get("corrected_text", "")}
            for s in request.raw_subtitles
        ]

        # 2. 提示词由词库驱动（harness_bridge/prompting.py 统一构造，codex/zcode 共用）
        prompt = build_correction_prompt(clean_input)

        success, output_str, latency = await self._run_codex_cli(prompt, timeout=60.0)
        if success:
            try:
                data = self._extract_json(output_str)
                updated_subtitles = data.get("subtitles", [])
                corrections_raw = data.get("corrections", [])
                
                # 校验并补齐字段
                if updated_subtitles:
                    corrections_summary = []
                    for c in corrections_raw:
                        corrections_summary.append(
                            SubtitleCorrectionItem(
                                subtitle_id=str(c.get("subtitle_id", "")),
                                original_text=str(c.get("original_text", "")),
                                corrected_text=str(c.get("corrected_text", "")),
                                changes=[{"from": str(c.get("original_text", "")), "to": str(c.get("corrected_text", "")), "reason": str(c.get("reason", "智能语义纠错"))}]
                            )
                        )

                    corr_text_map = {str(item.get("id")): item.get("corrected_text") for item in updated_subtitles if item.get("id")}
                    hl_map = {str(item.get("id")): item.get("highlight_keywords", []) for item in updated_subtitles if item.get("id")}

                    # 安全回填进完整字幕数据结构，完全保留原始精确物理时间戳；
                    # 大模型返回后再过一遍词库确定性纠偏兜底（幂等），防止模型漏纠或改错
                    final_subtitles = []
                    for orig in request.raw_subtitles:
                        seg = dict(orig)
                        sid = str(seg.get("id"))
                        if sid in corr_text_map and corr_text_map[sid]:
                            seg["corrected_text"] = corr_text_map[sid]
                        else:
                            seg["corrected_text"] = seg.get("corrected_text") or seg.get("raw_text", "")
                        seg["corrected_text"], _ = apply_glossary_corrections(str(seg["corrected_text"]))
                        
                        if sid in hl_map and isinstance(hl_map[sid], list):
                            existing_kw = seg.get("matched_keywords", []) or []
                            combined_kw = existing_kw + hl_map[sid]
                            seg["matched_keywords"] = list(dict.fromkeys(combined_kw))
                        final_subtitles.append(seg)

                    return HarnessCorrectionResponse(
                        updated_subtitles=final_subtitles,
                        corrections_summary=corrections_summary,
                        harness_engine_used="codex",
                        latency_ms=round(latency, 1)
                    )
            except Exception:
                pass

        # 触发优雅降级
        fallback_res = await self._fallback.correct_subtitles(request)
        fallback_res.harness_engine_used = "codex (fallback embedded)"
        fallback_res.latency_ms = round(latency, 1)
        return fallback_res

    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        """
        利用 Codex CLI 解析全能自然语言微调指令（改写文案、重选空镜、微调节奏）。
        """
        if not await self.is_available():
            fallback_res = await self._fallback.apply_natural_instruction(request)
            fallback_res.harness_engine_used = "codex (fallback embedded: cli not found)"
            return fallback_res

        project_state = request.current_project_state
        subtitles = project_state.get("subtitles", [])
        brolls = project_state.get("broll_replacements", [])
        materials = request.available_materials or []

        prompt = (
            "你是一个智能短视频剪辑师。用户正在微调驾校短视频工程。\n"
            "你的能力：根据用户的自然语言要求，支持修改字幕文本(文案润色)、重新分配空镜B-roll素材、或微调时间戳区间。\n"
            f"用户输入的微调指令：【{request.user_instruction}】\n\n"
            f"当前工程字幕：\n{json.dumps(subtitles, ensure_ascii=False)}\n\n"
            f"当前空镜分配：\n{json.dumps(brolls, ensure_ascii=False)}\n\n"
            f"可用素材库列表：\n{json.dumps(materials, ensure_ascii=False)}\n\n"
            "请严格以纯 JSON 格式输出修改结果，不要包含任何 markdown 或其他文本。格式如下：\n"
            "{\n"
            '  "explanation": "简明扼要的操作说明（例如：已将第1句文案修改为热情欢迎语，并将第2句关联的空镜头替换为体检分类素材）",\n'
            '  "updated_subtitles": [ ...更新后的完整字幕列表，若未变动请保留原有项... ],\n'
            '  "updated_brolls": [ ...更新后的完整空镜列表，若未变动请保留原有项... ]\n'
            "}"
        )

        success, output_str, latency = await self._run_codex_cli(prompt, timeout=60.0)
        if success:
            try:
                data = self._extract_json(output_str)
                explanation = data.get("explanation", f"已按指令【{request.user_instruction}】完成调整。")
                up_subs = data.get("updated_subtitles") or subtitles
                up_brolls = data.get("updated_brolls") or brolls
                return HarnessPlanResponse(
                    explanation=explanation,
                    updated_subtitles=up_subs,
                    updated_brolls=up_brolls,
                    harness_engine_used="codex",
                    latency_ms=round(latency, 1)
                )
            except Exception:
                pass

        # 触发降级
        fallback_res = await self._fallback.apply_natural_instruction(request)
        fallback_res.harness_engine_used = "codex (fallback embedded)"
        fallback_res.latency_ms = round(latency, 1)
        return fallback_res

    # generate_batch_variations 已删除：全项目无消费方，继承 base 默认显式报错
