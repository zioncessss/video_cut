from typing import Dict, Any, List, Optional
from app.core.config import DRIVING_SCHOOL_KEYWORDS

def match_keywords_in_segment(text: str) -> Dict[str, Any]:
    """
    基于驾校行业关键词库分析当前字幕命中的空镜分类与具体关键词
    优先级策略：体检 (medical) -> 场地 (venue) -> 教学 (lesson)
    """
    matched_cat: Optional[str] = None
    matched_words: List[str] = []

    # 优先匹配体检类特征词
    for kw in DRIVING_SCHOOL_KEYWORDS["medical"]:
        if kw in text:
            matched_words.append(kw)
    if matched_words:
        return {"matched_category": "medical", "matched_keywords": matched_words}

    # 其次匹配场地类特征词
    for kw in DRIVING_SCHOOL_KEYWORDS["venue"]:
        if kw in text:
            matched_words.append(kw)
    if matched_words:
        return {"matched_category": "venue", "matched_keywords": matched_words}

    # 匹配教学/练车类特征词
    for kw in DRIVING_SCHOOL_KEYWORDS["lesson"]:
        if kw in text:
            matched_words.append(kw)
    if matched_words:
        return {"matched_category": "lesson", "matched_keywords": matched_words}

    return {"matched_category": None, "matched_keywords": []}
