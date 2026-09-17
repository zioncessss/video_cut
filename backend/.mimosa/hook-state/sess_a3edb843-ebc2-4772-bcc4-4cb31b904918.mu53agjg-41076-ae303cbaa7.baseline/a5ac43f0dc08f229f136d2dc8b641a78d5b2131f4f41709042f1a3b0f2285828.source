from typing import Dict, Any, List, Optional
from app.core.config import get_driving_school_keywords

def match_keywords_in_segment(text: str) -> Dict[str, Any]:
    """
    基于词库（storage/glossary.json keywords）分析当前字幕命中的空镜分类与具体关键词，
    每次调用实时装载词库，编辑词库后立即生效。
    优先级策略：体检 (medical) -> 场地 (venue) -> 教学 (lesson)。
    同时跨所有类别扫描所有命中的专有词与强调词，用于字词行内高亮。
    """
    keywords = get_driving_school_keywords()
    matched_cat: Optional[str] = None
    all_matched_words: List[str] = []

    # 1. 判定空镜主分类（体检 > 场地 > 教学）
    for kw in keywords.get("medical", []):
        if kw in text:
            if not matched_cat:
                matched_cat = "medical"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    for kw in keywords.get("venue", []):
        if kw in text:
            if not matched_cat:
                matched_cat = "venue"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    for kw in keywords.get("lesson", []):
        if kw in text:
            if not matched_cat:
                matched_cat = "lesson"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    # 2. 扫描短视频爆款高光重点词 (一把过, 秘籍, 十分钟等)
    for kw in keywords.get("emphasis", []):
        if kw in text:
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    return {"matched_category": matched_cat, "matched_keywords": all_matched_words}

