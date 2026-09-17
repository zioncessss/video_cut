from typing import List, Dict, Any, Optional

def handle_material_fallback(
    matched_category: Optional[str],
    available_brolls: List[Any],
    talking_head_id: str
) -> Optional[str]:
    """
    当识别到关键词但该类别空镜素材缺失时，平滑降级处理：
    若有对应空镜素材则返回素材ID，若缺失则返回 None（保持口播画面，不报错崩溃）
    """
    if not matched_category or not available_brolls:
        return None
    return available_brolls[0].id if hasattr(available_brolls[0], 'id') else available_brolls[0]
