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


def infer_highlight_style(word: str, category: Optional[str] = None) -> Dict[str, str]:
    """根据词汇语义或既定分类推导最佳高亮色彩与类别"""
    import re
    w = word.strip()
    if category == "white" or w in ("千万不要", "一定要", "绝对", "必须", "真正", "全包"):
        return {"color": "#FFFFFF", "category": category or "white"}
    if category == "price" or re.search(r'\d+|元|费|价|全包|收费|包过|优惠|降价|免', w):
        return {"color": "#EF4444", "category": "price"}
    if category == "location" or re.search(r'校区|场地|考场|训练场|路|市|省|区|州', w):
        return {"color": "#38BDF8", "category": "location"}
    if category == "exam" or re.search(r'科[一二三四]|倒库|侧方|一把过|离合|打方向|教练', w):
        return {"color": "#FACC15", "category": "exam"}
    return {"color": "#FACC15", "category": category or "emphasis"}


def build_highlight_words(
    text: str,
    ai_keywords: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """
    高亮词多源合并工具（词库 ∪ AI 决策；manual 由用户在前端追加）：
    - 支持 AI 返回丰富对象 [{"word": "...", "color": "#...", "category": "..."}] 或纯字符串；
    - 地名（location）标亮青蓝 #38BDF8 或纯白 #FFFFFF；
    - 费用/价格（price）标鲜亮红 #EF4444 或醒目黄 #FACC15；
    - 白色高亮（white）标纯白 #FFFFFF 配合阴影增强质感；
    - 考点/动作（exam）标亮黄 #FACC15；
    - 词库命中的专名兜底标 glossary，AI 返回的自主决策标 ai；
    - AI 指定的特定颜色（如用户要求 AI 决定的白色或红色）具有最高视觉呈现优先级。
    返回 [{"word": "...", "source": "glossary|ai", "color": "...", "category": "..."}, ...]
    """
    merged: List[Dict[str, Any]] = []
    word_map: Dict[str, Dict[str, Any]] = {}

    def _add(word: str, source: str, color: Optional[str] = None, cat: Optional[str] = None):
        w = (word or "").strip()
        if not w:
            return
        if w in word_map:
            # 词库唯一事实源：若词库也命中该词，来源必须优先以 glossary 确定性为准
            if source == "glossary":
                word_map[w]["source"] = "glossary"
                if cat:
                    word_map[w]["category"] = cat
            return
        inferred = infer_highlight_style(w, cat)
        final_color = (color or inferred["color"]).upper()
        if not final_color.startswith("#"):
            final_color = f"#{final_color}"
        final_cat = cat or inferred["category"]
        entry = {
            "word": w,
            "source": source,
            "color": final_color,
            "category": final_cat
        }
        word_map[w] = entry
        merged.append(entry)

    # 1. 优先解析 AI 自主返回的高亮词及其色彩建议
    if ai_keywords and isinstance(ai_keywords, list):
        for item in ai_keywords:
            if isinstance(item, dict):
                w = str(item.get("word") or "").strip()
                c = item.get("color")
                cat = item.get("category")
                if w and w in text:
                    _add(w, "ai", color=c, cat=cat)
            elif isinstance(item, str) and item.strip() and item.strip() in text:
                _add(item.strip(), "ai")

    # 2. 词库全量关键词兜底扫描（按词长降序优先长词）
    keywords = get_driving_school_keywords()
    glossary_items: List[tuple] = []
    for cat_name, kws in keywords.items():
        if not isinstance(kws, list):
            continue
        for kw in kws:
            if isinstance(kw, str) and kw and kw in text:
                glossary_items.append((kw, cat_name))

    glossary_items.sort(key=lambda x: len(x[0]), reverse=True)
    for kw, cat_name in glossary_items:
        _add(kw, "glossary", cat=cat_name)

    return merged


