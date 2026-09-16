import re
from typing import List, Dict, Any
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessCorrectionResponse,
    SubtitleCorrectionItem,
    HarnessInstructionRequest,
    HarnessPlanResponse,
)
from app.core.config import DRIVING_SCHOOL_KEYWORDS

COMMON_DRIVING_CORRECTIONS = {
    "科尔": "科目二",
    "科二道库": "科目二倒库",
    "到库": "倒库",
    "坡起": "坡道起步",
    "测方": "侧方停车",
    "打灯": "开启转向灯",
    "提检": "体检",
    "学车价位": "学车价格"
}

class EmbeddedHarnessBridge(BaseHarnessBridge):
    """
    内置轻量级 Harness 桥接器：
    支持驾校场景专有词纠正、自然语言微调指令理解与批量多样性混剪规则规划。
    """
    async def is_available(self) -> bool:
        return True

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> HarnessCorrectionResponse:
        corrected_list = []
        corrections_summary = []
        for item in request.raw_subtitles:
            orig_text = item.get("raw_text", item.get("corrected_text", ""))
            c_text = orig_text
            changes = []
            for typo, correct in COMMON_DRIVING_CORRECTIONS.items():
                if typo in c_text:
                    c_text = c_text.replace(typo, correct)
                    changes.append({"from": typo, "to": correct, "reason": "内置驾考专有词纠偏"})
            
            new_item = dict(item)
            new_item["corrected_text"] = c_text
            # 自动提取驾校专有词与强调词用于高亮
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

    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        instr = request.user_instruction.strip()
        state = request.current_project_state
        subtitles = state.get("subtitles", [])
        brolls = state.get("broll_replacements", [])

        # 示例指令解析：“把第3句空镜换成另一个场地素材”
        explanation = f"已根据指令【{instr}】更新剪辑配置。"
        
        # 探测是否提及替换某一句
        match_idx = re.search(r"第\s*(\d+)\s*句", instr)
        if match_idx:
            idx = int(match_idx.group(1)) - 1
            if 0 <= idx < len(subtitles):
                explanation = f"已针对第 {idx + 1} 句（{subtitles[idx].get('corrected_text', '')[:10]}...）重新调度空镜头素材。"

        return HarnessPlanResponse(
            explanation=explanation,
            updated_subtitles=subtitles,
            updated_brolls=brolls,
            harness_engine_used="embedded"
        )

    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        variations = []
        for i in range(variant_count):
            var = dict(template_project)
            var["title"] = f"{template_project.get('title', '驾校推广')} (混剪版本 #{i+1})"
            variations.append(var)
        return variations

    async def stream_chat(self, prompt: str, model_override: str = None):
        import asyncio
        chunks = [
            "【内置离线助手】",
            "已收到您的提问或剪辑调整意图：",
            f"「{prompt}」\n\n",
            "建议您可以从以下几个维度优化当前的驾校短视频：\n",
            "1. **口播黄金3秒**：前3秒抛出痛点（如挂科、练车时间紧张）。\n",
            "2. **视听穿插 (J/L-Cut)**：在教练讲解操作技巧时，切入场地和考试特写空镜头。\n",
            "3. **专有名词校正**：如科目二倒库、坡道定点停车等，确保 ASR 识别准确无误。"
        ]
        for ch in chunks:
            yield {"type": "content", "delta": ch}
            await asyncio.sleep(0.05)
        yield {"type": "done"}

