from typing import Dict, Any, List, Optional
from app.core.config import get_driving_school_keywords

def match_keywords_in_segment(text: str) -> Dict[str, Any]:
    """
    基于词库（storage/glossary.json keywords）分析当前字幕命中的空镜分类与具体关键词，
    每次调用实时装载词库，编辑词库后立即生效。
    优先级策略：体验 (experience) -> 场地 (venue) -> 教学 (lesson)。
    同时跨所有类别扫描所有命中的专有词与强调词，用于字词行内高亮。
    兼容：词库键迁移期（medical -> experience）两键均可命中。
    """
    keywords = get_driving_school_keywords()
    matched_cat: Optional[str] = None
    all_matched_words: List[str] = []

    # 1. 判定空镜主分类（用户导演准则：练车学车细节 lesson > 场地实景 venue > 学员体验流程 experience）
    for kw in keywords.get("lesson", []):
        if kw in text:
            if not matched_cat:
                matched_cat = "lesson"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    for kw in keywords.get("venue", []):
        if kw in text:
            if not matched_cat:
                matched_cat = "venue"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    experience_kws = keywords.get("experience") or keywords.get("medical") or []
    for kw in experience_kws:
        if kw in text:
            if not matched_cat:
                matched_cat = "experience"
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    # 2. 扫描短视频爆款高光重点词 (一把过, 秘籍, 十分钟等)
    for kw in keywords.get("emphasis", []):
        if kw in text:
            if kw not in all_matched_words:
                all_matched_words.append(kw)

    return {"matched_category": matched_cat, "matched_keywords": all_matched_words}


def build_highlight_words(text: str, ai_keywords: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    高亮词三源合并工具（词库 ∪ AI；manual 由用户编辑持久层追加）：
    - 词库命中的词确定性兜底且来源优先标 glossary（跨所有类别扫描，含 location/emphasis）；
    - AI 判定词补位词库覆盖不到的自由表达（时间/数字/卖点），来源标 ai；
    - 长词优先、按词去重；同一词词库与 AI 同时命中时保留 glossary 来源。
    返回 [{"word": "...", "source": "glossary|ai"}, ...]
    """
    merged: List[Dict[str, str]] = []
    seen = set()

    def _add(word: str, source: str):
        w = (word or "").strip()
        if not w or w in seen:
            return
        seen.add(w)
        merged.append({"word": w, "source": source})

    keywords = get_driving_school_keywords()
    glossary_hits: List[str] = []
    for kws in keywords.values():
        if not isinstance(kws, list):
            continue
        for kw in kws:
            if isinstance(kw, str) and kw and kw in text:
                glossary_hits.append(kw)
    for w in sorted(glossary_hits, key=len, reverse=True):
        _add(w, "glossary")
    for w in sorted({k.strip() for k in (ai_keywords or []) if isinstance(k, str) and k.strip()}, key=len, reverse=True):
        _add(w, "ai")
    return merged

