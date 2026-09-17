from typing import List, Dict, Any
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessCorrectionResponse,
    SubtitleCorrectionItem,
)
from app.core.config import apply_glossary_corrections

class EmbeddedHarnessBridge(BaseHarnessBridge):
    """
    内置词库确定性纠偏引擎（Tier A 离线兜底）：
    仅做 storage/glossary.json 词库映射替换与关键词匹配，无任何网络与模型依赖。
    开放式任务（自由指令理解、聊天）不具备真实能力，一律显式报错，绝不返回预置话术假装成功。
    """
    async def is_available(self) -> bool:
        return True

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> HarnessCorrectionResponse:
        corrected_list = []
        corrections_summary = []
        for item in request.raw_subtitles:
            orig_text = item.get("raw_text", item.get("corrected_text", ""))
            c_text, changes = apply_glossary_corrections(orig_text)

            new_item = dict(item)
            new_item["corrected_text"] = c_text
            # 自动提取词库专有词与强调词用于高亮
            from app.native_engine.keyword_matcher import match_keywords_in_segment
            kw_res = match_keywords_in_segment(c_text)
            new_item["matched_keywords"] = kw_res.get("matched_keywords", [])
            new_item["matched_category"] = kw_res.get("matched_category")
            corrected_list.append(new_item)
            if changes:
                corrections_summary.append(
                    SubtitleCorrectionItem(
                        subtitle_id=item.get("id", ""),
                        original_text=orig_text,
                        corrected_text=c_text,
                        changes=changes
                    )
                )
        return HarnessCorrectionResponse(
            updated_subtitles=corrected_list,
            corrections_summary=corrections_summary,
            harness_engine_used="embedded",
            latency_ms=1.0
        )

    async def apply_natural_instruction(self, request):
        """开放式指令理解非本引擎能力，显式报错（覆盖 base 默认消息以给出更明确的指引）"""
        raise RuntimeError("内置词库引擎仅支持确定性纠偏，不支持开放式指令理解；请在设置页配置直连 API，或安装 codex / zcode 智能体")

    async def stream_chat(self, prompt: str, model_override: str = None):
        """聊天非本引擎能力，显式报错，绝不输出预置话术（迭代时抛出，由 chat SSE 错误通道带出）"""
        raise RuntimeError("内置词库引擎不支持聊天；请在设置页配置直连 API，或安装 codex / zcode 智能体")
        yield  # pragma: no cover  保持异步生成器签名
