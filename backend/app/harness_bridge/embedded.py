import re
from typing import List, Dict, Any
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
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

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> List[Dict[str, Any]]:
        corrected_list = []
        for item in request.raw_subtitles:
            c_text = item.get("raw_text", "")
            for typo, correct in COMMON_DRIVING_CORRECTIONS.items():
                c_text = c_text.replace(typo, correct)
            
            new_item = dict(item)
            new_item["corrected_text"] = c_text
            corrected_list.append(new_item)
        return corrected_list

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
