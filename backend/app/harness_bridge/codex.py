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
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessCorrectionResponse,
    SubtitleCorrectionItem,
    HarnessInstructionRequest,
    HarnessPlanResponse
)
from app.harness_bridge.embedded import EmbeddedHarnessBridge, COMMON_DRIVING_CORRECTIONS

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
        1. 优先通过本地 Codex 后端代理（15721 /v1/responses 真实端点）直连调用，毫秒级响应且规避 Windows CLI 管道挂起。
        2. 若代理不可用，回退至命令行 `codex exec`。
        """
        import httpx
        start_time = time.time()
        provider_cfg = config.get_codex_provider_config()
        base_url = provider_cfg.get("base_url", "http://127.0.0.1:15721/v1").rstrip("/")
        token = provider_cfg.get("token", "PROXY_MANAGED")
        active_model = (model_override or provider_cfg.get("model") or config.LLM_MODEL or "glm-5.3-flash").strip()

        # 1. 尝试直连本地后端代理 /v1/responses (wire_api="responses")
        try:
            url = f"{base_url}/responses"
            payload = {
                "model": active_model,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    output_text = ""
                    for item in data.get("output", []):
                        if item.get("type") == "message":
                            for c in item.get("content", []):
                                if c.get("type") == "output_text":
                                    output_text += c.get("text", "")
                    if output_text.strip():
                        latency_ms = (time.time() - start_time) * 1000
                        return True, output_text.strip(), latency_ms
        except Exception:
            pass

        # 2. 回退到 Codex CLI 进程执行
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
            async with httpx.AsyncClient() as client:
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

        # 组装 Prompt
        glossary_info = {
            "keywords": config.DRIVING_SCHOOL_KEYWORDS,
            "common_corrections": COMMON_DRIVING_CORRECTIONS
        }
        
        prompt = (
            "你是一个专业的驾校短视频口播字幕纠错与重点词提炼助手。\n"
            "任务：\n"
            "1. 针对驾校场景，修正 ASR 语音识别出的同音错别字、不规范简称或语法错漏。\n"
            "2. 针对短视频网感呈现，自动识别每一句中最需要视觉高亮强调的 1~2 个核心词或数字（例如：'科目二'、'一把过'、'五万平'、'十分钟'、'金牌教练'、'倒库'、'方便'等）。\n"
            f"行业专有名词与高频纠正规则参照：{json.dumps(glossary_info, ensure_ascii=False)}\n\n"
            "待校正的原始字幕列表：\n"
            f"{json.dumps(request.raw_subtitles, ensure_ascii=False)}\n\n"
            "请严格以单行或纯 JSON 格式输出，不要输出任何多余的开场白、解释或 markdown 标记。格式如下：\n"
            "{\n"
            '  "subtitles": [\n'
            '    {"id": "...", "start_time": 0.0, "end_time": 3.0, "raw_text": "...", "corrected_text": "...", "highlight_keywords": ["核心词1", "核心词2"]}\n'
            "  ],\n"
            '  "corrections": [\n'
            '    {"subtitle_id": "...", "original_text": "错字", "corrected_text": "正确字", "reason": "修改原因"}\n'
            "  ]\n"
            "}"
        )

        success, output_str, latency = await self._run_codex_cli(prompt, timeout=35.0)
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
                    # 保留或融合 AI 识别出的高亮词
                    for seg in updated_subtitles:
                        if "highlight_keywords" in seg and isinstance(seg["highlight_keywords"], list):
                            seg["matched_keywords"] = seg.get("matched_keywords", []) + seg["highlight_keywords"]
                    return HarnessCorrectionResponse(
                        updated_subtitles=updated_subtitles,
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

        success, output_str, latency = await self._run_codex_cli(prompt, timeout=35.0)
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

    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        return await self._fallback.generate_batch_variations(template_project, variant_count)
