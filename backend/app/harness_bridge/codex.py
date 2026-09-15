import asyncio
import json
import os
import re
import shutil
import tempfile
import time
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
        以非交互式执行 Codex CLI 并通过临时文件提取最终 Agent 回复。
        关键保障：显式传入 stdin=asyncio.subprocess.DEVNULL 避免 Windows 管道挂起。
        """
        if not await self.is_available():
            return False, "codex CLI not found in system PATH", 0.0

        temp_fd, temp_file_path = tempfile.mkstemp(suffix=".txt", prefix="codex_out_")
        os.close(temp_fd)

        cmd = [
            "codex", "exec",
            "--sandbox", "read-only",
            "--ephemeral",
            "-o", temp_file_path
        ]

        active_model = (model_override or config.LLM_MODEL or "").strip()
        if active_model:
            cmd.extend(["-m", active_model])

        cmd.append(prompt)

        start_time = time.time()
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

            # 读取临时文件内容
            last_message = ""
            if os.path.exists(temp_file_path):
                try:
                    with open(temp_file_path, "r", encoding="utf-8", errors="replace") as f:
                        last_message = f.read().strip()
                except Exception as ex:
                    last_message = ""

            # 若临时文件为空，备用检查 stdout
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

    async def ping(self, model_override: Optional[str] = None) -> Tuple[bool, str, float, str]:
        """连通性与模型可用性探针"""
        prompt = 'Output only a single valid JSON object: {"status": "ok", "agent": "codex"}. No other text or markdown.'
        success, out, latency = await self._run_codex_cli(prompt, timeout=12.0, model_override=model_override)
        if not success:
            return False, "", latency, out

        try:
            data = self._extract_json(out)
            if data.get("status") == "ok":
                detected_model = model_override or config.LLM_MODEL or "default (from config.toml)"
                return True, detected_model, latency, "Codex CLI 连通正常，探针响应成功"
            return False, "", latency, f"Invalid probe response: {out[:100]}"
        except Exception as e:
            return False, "", latency, f"Probe JSON parse failed: {str(e)}"

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
            "你是一个专业的驾校短视频口播字幕纠错助手。\n"
            "任务：针对驾校场景，修正 ASR 语音识别出的同音错别字、不规范简称或语法错漏。\n"
            f"行业专有名词与高频纠正规则参照：{json.dumps(glossary_info, ensure_ascii=False)}\n\n"
            "待校正的原始字幕列表：\n"
            f"{json.dumps(request.raw_subtitles, ensure_ascii=False)}\n\n"
            "请严格以单行或纯 JSON 格式输出，不要输出任何多余的开场白、解释或 markdown 标记。格式如下：\n"
            "{\n"
            '  "subtitles": [\n'
            '    {"id": "...", "start_time": 0.0, "end_time": 3.0, "raw_text": "...", "corrected_text": "..."}\n'
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
