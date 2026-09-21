import re
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

    # 2. 扫描短视频爆款高光重点词 (一把过, 秘籍, 十分钟等) 与核心价格保障词
    for kw in keywords.get("emphasis", []):
        if kw in text and kw not in all_matched_words:
            all_matched_words.append(kw)

    for kw in keywords.get("price", []):
        if kw in text and kw not in all_matched_words:
            all_matched_words.append(kw)

    return {"matched_category": matched_cat, "matched_keywords": all_matched_words}


# 负向停止词表：严禁打上高亮标签的无信息增量虚词、情态词、副词、连词与代词
HIGHLIGHT_STOPWORDS = {
    # 情态/语气/副词
    "一定要", "千万不要", "千万", "肯定", "可能", "其实", "应该", "非常", "特别", "十分", "这么", "那么",
    "已经", "还是", "真的", "必须", "绝对", "简直", "稍微", "大致", "平时", "经常", "往往",
    # 人称/指示代词
    "我们", "你们", "大家", "他们", "她们", "这个", "那个", "这些", "那些", "别人", "自己", "人家", "个人",
    # 连词/介词/助词
    "如果", "但是", "或者是", "或者", "的话", "而且", "虽然", "所以", "因为", "哪怕", "即使",
    "关于", "对于", "按照", "为了", "由此", "从而",
    # 泛义无信息动词/口语填充词
    "看到", "知道", "觉得", "告诉", "听说", "来到", "去找", "去做", "搞定", "怎么样",
    # 非收费无信息词（防'XX费'误伤）
    "浪费", "花费", "耗费", "白费"
}

# 提取词前缀虚词清洗表（防止匹配出'是保险费'、'那这个费用'、'练车的费用'等带语法残渣的词）
PREFIXES_TO_STRIP = (
    "是", "那", "这", "的", "个", "有", "包含", "除", "交", "收", "免", "无",
    "做", "去", "在", "不", "关于", "对于", "全部的", "总共", "大概", "通常",
    "也就是", "咱们", "去到", "场练车的", "练车的"
)

def clean_highlight_term(w: str) -> str:
    """去除分词正则可能吞入的语法虚词前缀"""
    w = (w or "").strip()
    changed = True
    while changed and len(w) > 2:
        changed = False
        for p in PREFIXES_TO_STRIP:
            if w.startswith(p) and len(w) - len(p) >= 2:
                w = w[len(p):].strip()
                changed = True
                break
    return w


# 核心地域/校区词库（短视频同城推流第一信任抓手，青蓝色 #38BDF8）
DOMAIN_LOCATION_WORDS = [
    "杭州", "湖州", "宁波", "绍兴", "嘉兴", "温州", "金华", "台州", "丽水", "衢州", "舟山",
    "余杭", "萧山", "临平", "西湖", "滨江", "拱墅", "上城", "钱塘", "富阳", "临安",
    "车管所", "训练场", "场地", "考场", "校区", "五万平", "模拟场"
]

DOMAIN_LOCATION_PATTERNS = [
    re.compile(r'(?:在|去|来|位于|靠近|到)([\u4e00-\u9fa5]{2,4})(?:这边|这里|本地|市区|县城|中心|校区|场地|考场)'),
    re.compile(r'([^\s，。？！]{2,3}(?:市|区|县|镇|街道))'),
]

# 核心费用/数字正则（金额是学员最核心关切，鲜亮红 #EF4444）
DOMAIN_PRICE_PATTERNS = [
    re.compile(r'[一二两三四五六七八九十几个]+[百千万](?:[一二两三四五六七八九十]+(?:[百千万]|块|元)?)?[多块元]?'),
    re.compile(r'\d+多?[块元]?'),
    re.compile(r'几百块钱'),
    re.compile(r'(?:[^\s，。？！]{1,4}(?:费用|费|明细表|明细))'),
]

# 核心收费/痛点/避坑词（完播率与信任感核心锚点，鲜亮红 #EF4444）
DOMAIN_PRICE_TERMS = [
    "练车费", "补训费", "燃油费", "模拟费", "报名费", "学费", "补考费", "体检费", "加急费", "工本费", "打卡费", "场地费",
    "考试费", "四科考试费", "理论培训费", "培训费", "保险费", "面签费", "费用明细表", "费用明细", "明细表", "多少钱",
    "练车费用", "考场练车", "后期收费", "乱收费", "隐形消费", "隐形的坑", "无隐形消费", "一口价", "全包", "避雷帖", "避雷", "踩坑",
    "套路", "价格低到离谱", "低到离谱", "再便宜", "交完钱", "收费", "价格", "吃拿卡要",
    "越承诺套路越深"
]

# 核心考点/技能/教练词（亮黄 #FACC15）
DOMAIN_EXAM_TERMS = [
    "科目二", "科目三", "科目一", "科目四", "科二", "科三", "科一", "科四",
    "倒库", "侧方停车", "侧方", "坡道起步", "打方向", "离合", "拿证", "两三个月",
    "一把过", "手把手教学", "免排队", "极速拿证", "教练", "金牌教练", "学车", "驾校",
    "考驾照", "驾照", "练车", "滴滴我", "联系我"
]

# 纯白大字视觉强调词（纯白 #FFFFFF）
DOMAIN_WHITE_TERMS = [
    "大幅度下降", "上千个学员"
]


def extract_rule_highlight_words(text: str) -> List[Dict[str, Any]]:
    """
    全自动精准短视频高亮词规则引擎：
    按 费用(price) > 地名(location) > 考点(exam) > 强调(white) 优先级提取，
    严格执行负向过滤与前缀虚词清洗，自动消除重叠区间，单句最多提取 1~2 个最关键的高光抓手词。
    """
    if not text:
        return []

    candidates: List[Dict[str, Any]] = []

    # 1. 费用与痛点词
    for p in DOMAIN_PRICE_TERMS:
        if p in text and p not in HIGHLIGHT_STOPWORDS:
            candidates.append({"word": p, "color": "#EF4444", "category": "price", "priority": 100})

    for pat in DOMAIN_PRICE_PATTERNS:
        for m in pat.finditer(text):
            raw_w = m.group(1).strip() if m.groups() else m.group(0).strip()
            w = clean_highlight_term(raw_w)
            if len(w) >= 2 and w not in HIGHLIGHT_STOPWORDS and not w.isdigit():
                candidates.append({"word": w, "color": "#EF4444", "category": "price", "priority": 95})

    # 2. 地名/区域（核心静态城市 + 通配区县正则启发式）
    for loc in DOMAIN_LOCATION_WORDS:
        if loc in text and loc not in HIGHLIGHT_STOPWORDS:
            candidates.append({"word": loc, "color": "#38BDF8", "category": "location", "priority": 90})

    for pat in DOMAIN_LOCATION_PATTERNS:
        for m in pat.finditer(text):
            raw_w = m.group(1).strip() if m.groups() else m.group(0).strip()
            w = clean_highlight_term(raw_w)
            if len(w) >= 2 and w not in HIGHLIGHT_STOPWORDS:
                candidates.append({"word": w, "color": "#38BDF8", "category": "location", "priority": 88})

    # 3. 考点/教练/动作
    for ex in DOMAIN_EXAM_TERMS:
        if ex in text and ex not in HIGHLIGHT_STOPWORDS:
            candidates.append({"word": ex, "color": "#FACC15", "category": "exam", "priority": 80})

    # 4. 纯白大字视觉强调
    for wh in DOMAIN_WHITE_TERMS:
        if wh in text and wh not in HIGHLIGHT_STOPWORDS:
            candidates.append({"word": wh, "color": "#FFFFFF", "category": "white", "priority": 75})

    # 依优先级和词长降序排列，消除重叠，取 top 1~2
    candidates.sort(key=lambda x: (x["priority"], len(x["word"])), reverse=True)

    selected: List[Dict[str, Any]] = []
    occupied_spans: List[tuple] = []
    for c in candidates:
        w = c["word"]
        start_idx = text.find(w)
        if start_idx == -1:
            continue
        end_idx = start_idx + len(w)

        # 检查是否与已选词重叠
        overlap = any(max(start_idx, s) < min(end_idx, e) for s, e in occupied_spans)
        if not overlap:
            occupied_spans.append((start_idx, end_idx))
            selected.append({
                "word": w,
                "source": "glossary",
                "color": c["color"],
                "category": c["category"]
            })
            if len(selected) >= 2:
                break

    return selected


def infer_highlight_style(word: str, category: Optional[str] = None) -> Dict[str, str]:
    """根据词汇语义或既定分类推导最佳高亮色彩与类别"""
    import re
    w = word.strip()
    cat_lower = (category or "").lower()
    if cat_lower == "white" or w in ("全包", "真实", "痛点", "大幅度下降", "上千个学员"):
        return {"color": "#FFFFFF", "category": "white"}
    if cat_lower == "price" or re.search(r'\d+|两千|三千|四千|元|费|价|一口价|收费|包过|优惠|降价|免|隐形消费|乱收费|吃拿卡要|套路|坑|踩坑|避雷|避坑', w):
        return {"color": "#EF4444", "category": "price"}
    if cat_lower == "location" or (
        re.search(r'校区|场地|考场|训练场|市|省|区|州|杭州|湖州|余杭|萧山|临平|西湖', w)
        or (re.search(r'路', w) and "套路" not in w)
    ):
        return {"color": "#38BDF8", "category": "location"}
    if cat_lower == "exam" or re.search(r'科[一二三四]|倒库|侧方|一把过|离合|打方向|教练|手把手|极速拿证|免排队', w):
        return {"color": "#FACC15", "category": "exam"}
    return {"color": "#FACC15", "category": category or "emphasis"}


def build_highlight_words(
    text: str,
    ai_keywords: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """
    高亮词多源合并工具（AI 决策 ∪ 词库规则引擎 ∪ glossary 专名词；manual 由前端交互追加）：
    - 优先采用 AI 丰富决策 [{"word": "...", "color": "#...", "category": "..."}]；
    - 无 AI 或直通 ASR 模式下自动触发高精短视频规则引擎 extract_rule_highlight_words；
    - 严格执行负向停止词过滤（自动剔除'一定要'、'其实'、'我们'等虚词）；
    - 地名（location）标亮青蓝 #38BDF8；
    - 费用/痛点（price）标鲜亮红 #EF4444；
    - 考点/教练（exam）标亮黄 #FACC15；
    - 白色高亮（white）标纯白 #FFFFFF；
    - 控制单句高光密度（单句 1~2 个最关键词，宁缺毋滥）。
    """
    merged: List[Dict[str, Any]] = []
    word_map: Dict[str, Dict[str, Any]] = {}

    def _add(word: str, source: str, color: Optional[str] = None, cat: Optional[str] = None):
        w = (word or "").strip()
        if not w:
            return
        if w in HIGHLIGHT_STOPWORDS:
            return
        if len(w) <= 1 and not w.isdigit() and w not in ("坑", "雷"):
            return
        if w in word_map:
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

    # 2. 触发高精短视频规则引擎（地名/费用/考点/痛点）
    rule_highlights = extract_rule_highlight_words(text)
    for rh in rule_highlights:
        if rh["word"] not in word_map:
            _add(rh["word"], "glossary", color=rh["color"], cat=rh["category"])

    # 3. 词库 glossary.json 关键词兜底扫描（按词长降序）
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

    # 4. 区间去重（若未传 ai_keywords 限制单句最多 2 个核心高亮词，避免视觉过载）
    max_allowed = max(len(ai_keywords), 2) if (ai_keywords and isinstance(ai_keywords, list)) else 2
    final_selected: List[Dict[str, Any]] = []
    occupied_spans: List[tuple] = []
    for item in merged:
        w = item["word"]
        idx = text.find(w)
        if idx == -1:
            continue
        end_idx = idx + len(w)
        overlap = any(max(idx, s) < min(end_idx, e) for s, e in occupied_spans)
        if not overlap:
            occupied_spans.append((idx, end_idx))
            final_selected.append(item)
            if len(final_selected) >= max_allowed:
                break

    return final_selected



