"""AI 分镜决策：解析、确定性校验裁剪（双保险）、稳定性编排与关键词规则降级。

设计依据 specs/005-auto-edit-pipeline/research.md R8（真实口播风格模型）：
四类硬性不切区（开场钩子/价格手势句/结尾CTA/情绪叙事）在 validate_and_clip 兜底；
节奏与覆盖（防频闪合并、单镜 2~6s 钳制、总覆盖收敛约 2/3）由 plan_stable_windows 编排层统一负责。
AI 输出永不直接信任，必须经过确定性校验与编排。
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.harness_bridge import llm_client
from app.models.entities import MaterialCategory, SceneDecision, BrollCueItem

VALID_BROLL = {c.value for c in (MaterialCategory.VENUE, MaterialCategory.EXPERIENCE, MaterialCategory.LESSON)}

# 价格手势句：画面比划报价是内容本体，切走即内容丢失
_PRICE_GESTURE_RE = re.compile(r"这个数|这个价|这么多|比这个|价格?是?这个")
# 结尾行动召唤话术（part 推断兜底，AI 未标或误标时纠正）
_CTA_RE = re.compile(r"滴滴我|找我聊|点红心|点个红心|关注一下|觉得怎么样|报名都没有关系|私信我|评论区")

MAX_BROLL_RATIO = 0.70
DEFAULT_FALLBACK_RATIO = 0.60   # 降级规则：默认切句长的 60%
HARD_CUT_TRANSITION = 0.0

# ===== 成片分镜编排（体验硬约束，凌驾于 AI 决策之上）=====
MIN_WINDOW_SECONDS = 2.0    # 频闪下限：短于该值的单镜观感为"闪一下"，必须延展或丢弃
MAX_WINDOW_SECONDS = 6.0    # 单镜单调上限：超长分镜截断
HARD_MAX_WINDOW_SECONDS = 10.0  # 覆盖率不足下限时的延展硬上限（连续镜头不闪切，可接受）
MERGE_GAP_SECONDS = 0.8     # 相邻窗口间隔小于此值合并或缝合为连续分镜，避免快闪交替
MIN_TALKING_HEAD_SECONDS = 1.8 # 口播真人出镜最小自然时长（单整句下限，杜绝 0.x 秒闪回主画面）
EDGE_GAP_SECONDS = 0.0      # 严禁人为刻意制造 0.3s 画面闪烁间隙
COVERAGE_MIN = 0.40         # 空镜总时长占片长比例下限
COVERAGE_MAX = 0.70         # 占比上限
COVERAGE_TARGET = 0.65      # 目标中心（60%~70% 黄金区间）


def plan_stable_windows(raw_spans: List[Dict[str, Any]], total_duration: float) -> List[Dict[str, Any]]:
    """把逐句零散的空镜窗口编排成稳定的成片分镜时间线（确定性，无 AI）。

    输入 raw_spans: [{start_time, end_time, material_category}]（AI/关键词决策的原始窗口）。
    编排规则：
      1) 相邻窗口间隔 < MERGE_GAP 时合并或连切，消除"闪一下闪一下"的快闪交替；
      2) 单镜时长钳制到 [MIN, MAX]：太长截断；太短向右延展（J-cut：画面延续、口播继续），
         延展不到下限则整窗丢弃——宁可少切不可闪切；
      3) 总覆盖时长收敛到 [COVERAGE_MIN, COVERAGE_TARGET]×片长（约 2/3）：
         不足时按剩余空间向右轮转延展，超上限时从最长窗开始截断（不低于下限）；
      4) 防频闪闪切消除：杜绝任何 0 < gap < MIN_TALKING_HEAD_SECONDS (1.8s) 的微小口播闪烁，
         缝合成无缝连切（空镜1切空镜2）。
    """
    total_duration = max(0.0, float(total_duration or 0.0))
    spans: List[Dict[str, Any]] = []
    for s in raw_spans or []:
        try:
            start = max(0.0, float(s.get("start_time", 0.0)))
            end = float(s.get("end_time", 0.0))
        except (TypeError, ValueError):
            continue
        if end - start <= 0.05:
            continue
        if total_duration > 0:
            end = min(end, total_duration)
        if end <= start:
            continue
        spans.append({"start_time": start, "end_time": end,
                      "material_category": s.get("material_category")})
    spans.sort(key=lambda w: w["start_time"])
    if not spans:
        return []
    if total_duration <= 0:
        total_duration = max(w["end_time"] for w in spans)

    # 1. 近邻合并与连续无缝缝合（消除快闪交替）
    merged: List[Dict[str, Any]] = []
    for w in spans:
        if not merged:
            merged.append(dict(w))
            continue
        prev = merged[-1]
        gap = w["start_time"] - prev["end_time"]
        if gap < MERGE_GAP_SECONDS:
            merged_dur = max(prev["end_time"], w["end_time"]) - prev["start_time"]
            if w.get("material_category") == prev.get("material_category") and merged_dur <= MAX_WINDOW_SECONDS:
                # 同品类极小间隔且总时长不超单镜上限：直接融为一个连续分镜
                prev["end_time"] = max(prev["end_time"], w["end_time"])
            else:
                # 异类或超长同类：消除间隙，无缝连切（空镜1切空镜2，保留多机位切换与语义完整）
                prev["end_time"] = w["start_time"]
                merged.append(dict(w))
        else:
            merged.append(dict(w))

    # 2. 单镜时长钳制：太长截断；太短向右延展至下限，延不动则丢弃
    clamped: List[Dict[str, Any]] = []
    for i, w in enumerate(merged):
        start = w["start_time"]
        next_start = merged[i + 1]["start_time"] if i + 1 < len(merged) else total_duration
        room_right = max(start, next_start)
        dur = w["end_time"] - start
        if dur < MIN_WINDOW_SECONDS:
            extended_end = min(start + MAX_WINDOW_SECONDS, room_right, total_duration)
            if extended_end - start >= MIN_WINDOW_SECONDS:
                clamped.append({"start_time": start, "end_time": extended_end,
                                "material_category": w["material_category"]})
            # 延展后仍不足下限 → 丢弃（宁可少切不可闪切）
            continue
        end = min(w["end_time"], start + MAX_WINDOW_SECONDS, room_right)
        if end - start < MIN_WINDOW_SECONDS:
            end = w["end_time"]  # 右侧空间不足时保留原长
        clamped.append({"start_time": start, "end_time": end, "material_category": w["material_category"]})
    if not clamped:
        return []

    # 3. 覆盖率收敛
    def _span(ws: List[Dict[str, Any]]) -> float:
        return sum(w["end_time"] - w["start_time"] for w in ws)

    result = clamped
    upper = COVERAGE_MAX * total_duration
    target = COVERAGE_TARGET * total_duration
    # 3a. 超上限：从最长窗开始截（不低于下限），裁不动则整窗移除
    while result and _span(result) > upper + 1e-6:
        w = max(result, key=lambda x: x["end_time"] - x["start_time"])
        cur = w["end_time"] - w["start_time"]
        cut = min(cur - MIN_WINDOW_SECONDS, _span(result) - upper)
        if cut <= 1e-6:
            result.remove(w)
        else:
            w["end_time"] -= cut
    # 3b. 低于目标：轮转向右延展。常规上限 MAX；覆盖率仍低于下限时放宽到
    #     HARD_MAX（连续镜头不闪切，可接受），确保覆盖率硬性达标
    while _span(result) < max(target, COVERAGE_MIN * total_duration) - 1e-6:
        progressed = False
        span_now = _span(result)
        hard_cap = HARD_MAX_WINDOW_SECONDS if span_now < COVERAGE_MIN * total_duration else MAX_WINDOW_SECONDS
        for i, w in enumerate(result):
            if _span(result) >= max(target, COVERAGE_MIN * total_duration) - 1e-6:
                break
            cur = w["end_time"] - w["start_time"]
            if cur >= hard_cap - 1e-6:
                continue
            next_start = result[i + 1]["start_time"] if i + 1 < len(result) else total_duration
            new_end = min(w["start_time"] + hard_cap, max(next_start, w["end_time"]), total_duration)
            grow = min(new_end - w["end_time"], max(target, COVERAGE_MIN * total_duration) - _span(result))
            if grow > 1e-6:
                w["end_time"] += grow
                progressed = True
        if not progressed:
            break

    # 4. 防频闪消除：杜绝任何 0 < gap < MIN_TALKING_HEAD_SECONDS (1.8s) 的微小口播闪烁
    # 连着空镜切也可以，但绝不能给主镜头一个 0.x 秒瞬间跳转的时间
    bridged: List[Dict[str, Any]] = []
    for w in sorted(result, key=lambda x: x["start_time"]):
        if not bridged:
            bridged.append(w)
            continue
        prev = bridged[-1]
        gap = round(w["start_time"] - prev["end_time"], 3)
        if gap <= 0.05:
            prev["end_time"] = w["start_time"]
            bridged.append(w)
        elif gap < MIN_TALKING_HEAD_SECONDS:
            prev["end_time"] = w["start_time"]
            bridged.append(w)
        else:
            bridged.append(w)
    result = bridged

    return [
        {"start_time": round(w["start_time"], 3), "end_time": round(w["end_time"], 3),
         "material_category": w["material_category"]}
        for w in sorted(result, key=lambda x: x["start_time"])
    ]


def load_fixture_subtitles(path: Path) -> List[Dict[str, Any]]:
    """加载测试固件（每行 id|start|end|text），仅测试使用"""
    subs = []
    for line in Path(path).read_text(encoding="utf-8").strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            subs.append({
                "id": parts[0],
                "start_time": float(parts[1]),
                "end_time": float(parts[2]),
                "corrected_text": parts[3],
            })
    return subs


class CueList(list):
    """携带 video_title 与 highlights 的分镜指示清单列表，100% 兼容 list 行为"""
    def __init__(self, iterable=(), video_title: Optional[str] = None, highlights: Optional[Dict[str, Any]] = None):
        super().__init__(iterable)
        self.video_title = video_title
        self.highlights = highlights or {}


def parse_cue_sheet(raw: str) -> CueList:
    """从大模型稀疏输出中解析 broll_cues 列表、短视频爆款标题及全篇自主提取的高光词 highlights"""
    data = llm_client.extract_json(raw)
    if not isinstance(data, dict):
        return CueList([])
    video_title = str(data.get("video_title") or "").strip() or None
    raw_highlights = data.get("highlights")
    highlights_map: Dict[str, List[Dict[str, Any]]] = {}
    if isinstance(raw_highlights, dict):
        for k, v in raw_highlights.items():
            if isinstance(v, list):
                valid_items = []
                for item in v:
                    if isinstance(item, dict) and item.get("word"):
                        valid_items.append(item)
                    elif isinstance(item, str) and item.strip():
                        valid_items.append({"word": item.strip()})
                if valid_items:
                    highlights_map[str(k)] = valid_items

    items = data.get("broll_cues")
    if not isinstance(items, list):
        if isinstance(data, list):
            items = data
        else:
            return CueList([], video_title=video_title, highlights=highlights_map)

    result = CueList([], video_title=video_title, highlights=highlights_map)
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            st = float(it.get("start_time", 0.0))
            et = float(it.get("end_time", 0.0))
            cat_str = str(it.get("category", "")).lower().strip()
            if cat_str in VALID_BROLL and et > st:
                result.append(BrollCueItem(
                    start_time=round(st, 2),
                    end_time=round(et, 2),
                    category=MaterialCategory(cat_str),
                    visual_intent=str(it.get("visual_intent", ""))
                ))
        except (ValueError, TypeError):
            continue
    return result


def generate_fallback_video_title(subtitles: List[Dict[str, Any]]) -> str:
    """基于口播前序黄金钩子与核心关键词，零延迟确定性提炼短视频爆款标题"""
    if not subtitles:
        return "短视频精剪"

    texts = [str(s.get("corrected_text") or s.get("raw_text") or "").strip() for s in subtitles[:4]]
    clean_texts = [re.sub(r"[，,。？！?!…\s]+$", "", t) for t in texts if t]

    if not clean_texts:
        return "短视频精剪"

    KEY_TOPICS = ("改革", "一口价", "学车", "驾校", "教练", "报名", "拿证", "科目二", "科目三", "避雷", "踩坑", "收费", "技巧", "秘籍")

    topic_clauses = [t for t in clean_texts if any(k in t for k in KEY_TOPICS)]
    if len(topic_clauses) >= 2:
        c1, c2 = topic_clauses[0], topic_clauses[1]
        c2_clean = re.sub(r"^(我们现在|大家|其实|另外|还有|也就是说)", "", c2)
        combined = f"{c1}·{c2_clean}"
        if len(combined) <= 18:
            return combined
        if len(c1) <= 16:
            return c1
        return c1[:16]

    if topic_clauses:
        best = topic_clauses[0]
        return best[:18] if len(best) > 18 else best

    first = clean_texts[0]
    return first[:16] if len(first) > 16 else first


def parse_decisions(raw: str) -> List[Dict[str, Any]]:
    """从模型输出提取决策列表，容忍 markdown 包裹；解析失败返回空（由调用方降级）"""
    data = llm_client.extract_json(raw)
    if isinstance(data, dict) and isinstance(data.get("decisions"), list):
        return [d for d in data["decisions"] if isinstance(d, dict)]
    return []


def _infer_part(index: int, text: str, declared: Optional[str], start_time: float = 0.0) -> str:
    """part 推断：开场 1.8s 以内的首句判定为 hook；CTA 话术正则兜底；其余尊重 AI 声明"""
    if start_time < 1.8 and index == 0:
        return "hook"
    if _CTA_RE.search(text or ""):
        return "cta"
    return declared if declared in ("hook", "body", "cta") else "body"


def _is_price_gesture(text: str) -> bool:
    return bool(_PRICE_GESTURE_RE.search(text or ""))


def validate_cue_prohibited_zones(subtitles: List[Dict[str, Any]], cues: List[BrollCueItem]) -> List[BrollCueItem]:
    """
    确定性校验三大禁切红线：
    1. 开场 1.8s 以内口播真人亮相绝对禁止切空镜；
    2. 报价手势句区间绝对不切；
    3. 结尾行动召唤（CTA）区间绝对不切。
    """
    prohibited_ranges: List[tuple] = [(0.0, 1.8)]  # 开场 1.8s 红线

    for s in subtitles:
        text = str(s.get("corrected_text") or s.get("raw_text") or "")
        st = float(s.get("start_time", 0.0))
        et = float(s.get("end_time", st))
        if _is_price_gesture(text) or _CTA_RE.search(text):
            prohibited_ranges.append((st, et))

    valid_cues: List[BrollCueItem] = []
    for c in cues:
        c_st = c.start_time
        c_et = c.end_time

        # 开场保护
        if c_st < 1.8:
            if c_et - 1.8 >= MIN_WINDOW_SECONDS:
                c_st = 1.8
            else:
                continue

        # 校验与禁切句重叠
        overlap = False
        for p_start, p_end in prohibited_ranges:
            if p_start == 0.0 and p_end == 1.8:
                continue
            overlap_dur = max(0.0, min(c_et, p_end) - max(c_st, p_start))
            if overlap_dur > 0.3:
                overlap = True
                break

        if not overlap and (c_et - c_st >= MIN_WINDOW_SECONDS):
            valid_cues.append(BrollCueItem(
                start_time=round(c_st, 2),
                end_time=round(c_et, 2),
                category=c.category,
                visual_intent=c.visual_intent
            ))

    return valid_cues


def snap_cues_to_words(subtitles: List[Dict[str, Any]], cues: List[BrollCueItem]) -> List[BrollCueItem]:
    """将大模型输出的粗时间戳吸附至最近的自然语句边缘（优先整句起止点，其次逗号/停顿半句切分点）"""
    if not subtitles or not cues:
        return cues

    # 1. 提取整句边界（一级锚点）
    sentence_starts = []
    sentence_ends = []
    # 2. 提取子句停顿边界（二级锚点：逗号、停顿 >= 0.18s）
    clause_boundaries = []
    # 3. 词级边界（三级兜底）
    word_boundaries = []

    for s in subtitles:
        st = float(s.get("start_time", 0.0))
        et = float(s.get("end_time", 0.0))
        sentence_starts.append(st)
        sentence_ends.append(et)

        words = s.get("words") or []
        for i, w in enumerate(words):
            if not isinstance(w, dict):
                continue
            w_st = float(w.get("start", 0.0))
            w_et = float(w.get("end", 0.0))
            w_text = str(w.get("word") or "")
            word_boundaries.extend([w_st, w_et])
            # 标点逗号/顿号/分号/感叹号
            if any(p in w_text for p in ("，", ",", "、", "；", ";", "！", "!", "？", "?", "。")):
                clause_boundaries.append(w_et)
            # 词间停顿 >= 0.18s
            if i + 1 < len(words) and isinstance(words[i + 1], dict):
                next_st = float(words[i + 1].get("start", 0.0))
                if next_st - w_et >= 0.18:
                    clause_boundaries.append(round((w_et + next_st) / 2.0, 2))

    sentence_starts = sorted(list(set(sentence_starts)))
    sentence_ends = sorted(list(set(sentence_ends)))
    clause_boundaries = sorted(list(set(clause_boundaries)))
    word_boundaries = sorted(list(set(word_boundaries)))

    def _snap_timestamp(t: float, is_start: bool) -> float:
        primary = sentence_starts if is_start else sentence_ends
        # 1. 优先在 0.8s 内吸附整句边缘
        close_sent = [b for b in primary if abs(b - t) <= 0.8]
        if close_sent:
            return min(close_sent, key=lambda b: abs(b - t))

        # 2. 其次在 0.5s 内吸附半句/停顿边缘
        close_clause = [b for b in clause_boundaries if abs(b - t) <= 0.5]
        if close_clause:
            return min(close_clause, key=lambda b: abs(b - t))

        # 3. 再次在 0.3s 内吸附物理词边缘
        close_word = [b for b in word_boundaries if abs(b - t) <= 0.3]
        if close_word:
            return min(close_word, key=lambda b: abs(b - t))

        # 4. 定位 t 所在的整句，吸附到该句的子句或起止端点（实现"尽量是一句话，半句话的时候再切"）
        for s in subtitles:
            st = float(s.get("start_time", 0.0))
            et = float(s.get("end_time", 0.0))
            if st <= t <= et:
                internal_clauses = [cb for cb in clause_boundaries if st < cb < et]
                if internal_clauses:
                    return min(internal_clauses, key=lambda cb: abs(cb - t))
                mid = (st + et) / 2.0
                if is_start:
                    return st if t < mid else et
                else:
                    return et if t > mid else st

        all_pts = sentence_starts + sentence_ends
        if all_pts:
            return min(all_pts, key=lambda p: abs(p - t))

        return t

    snapped: List[BrollCueItem] = []
    for c in cues:
        best_start = _snap_timestamp(c.start_time, is_start=True)
        best_end = _snap_timestamp(c.end_time, is_start=False)
        if best_end > best_start + 1.0:
            snapped.append(BrollCueItem(
                start_time=round(best_start, 2),
                end_time=round(best_end, 2),
                category=c.category,
                visual_intent=c.visual_intent
            ))
        else:
            snapped.append(c)
    return snapped


def plan_dual_layer_broll(
    subtitles: List[Dict[str, Any]],
    cues: List[BrollCueItem],
    total_duration: float,
    target_coverage: float = 0.65,
    available_categories: Optional[List[MaterialCategory]] = None
) -> List[Dict[str, Any]]:
    """
    双层分镜编排引擎：
    第一层：强相关语义精准锚定（来自 LLM broll_cues 或关键词命中），吸附整句/半句边缘并严格执行三大禁切区红线；
    第二层：在未覆盖的自由正文区间自适应铺设 3~5 秒连续镜头（优先按完整句子组合），硬性确保 1~2 分钟成片达到 60%~70% 黄金覆盖率；
    成片防频闪守则：绝不在两个分镜之间留出 0.x 秒的闪切主画面（要么无缝连切 gap=0，要么真人完整说一整句 >= 1.8s）。
    """
    total_duration = max(0.0, float(total_duration or 0.0))
    if total_duration <= 0 and subtitles:
        total_duration = max(float(s.get("end_time", 0.0)) for s in subtitles)

    if not available_categories:
        available_categories = [MaterialCategory.VENUE, MaterialCategory.LESSON, MaterialCategory.EXPERIENCE]

    # 1. 禁切区保护与时间戳吸附（整句/半句停顿优先）
    valid_cues = validate_cue_prohibited_zones(subtitles, cues)
    snapped_cues = snap_cues_to_words(subtitles, valid_cues)

    current_spans: List[Dict[str, Any]] = [
        {
            "start_time": c.start_time,
            "end_time": c.end_time,
            "material_category": c.category
        }
        for c in snapped_cues
    ]

    # 2. 收集所有不可切区间
    prohibited_intervals: List[tuple] = [(0.0, 1.8)]  # 开场 1.8s
    for s in subtitles:
        text = str(s.get("corrected_text") or s.get("raw_text") or "")
        st = float(s.get("start_time", 0.0))
        et = float(s.get("end_time", st))
        if _is_price_gesture(text) or _CTA_RE.search(text):
            prohibited_intervals.append((st, et))

    occupied_intervals = list(prohibited_intervals)
    for sp in current_spans:
        occupied_intervals.append((sp["start_time"], sp["end_time"]))

    occupied_intervals.sort(key=lambda x: x[0])
    merged_occupied: List[tuple] = []
    for start, end in occupied_intervals:
        if merged_occupied and start <= merged_occupied[-1][1]:
            merged_occupied[-1] = (merged_occupied[-1][0], max(merged_occupied[-1][1], end))
        else:
            merged_occupied.append((max(0.0, start), min(total_duration, end)))

    # 3. 寻找正文中的自由区间
    free_intervals: List[tuple] = []
    curr_pos = 1.8
    for occ_start, occ_end in merged_occupied:
        if occ_end <= curr_pos:
            continue
        if occ_start > curr_pos:
            free_intervals.append((curr_pos, min(total_duration, occ_start)))
        curr_pos = max(curr_pos, occ_end)
    if curr_pos < total_duration:
        free_intervals.append((curr_pos, total_duration))

    # 4. 第二层自适应铺底：在 free intervals 中按 3.0~5.5 秒节奏插入分镜（优先按字幕整句编排）
    target_coverage = max(0.40, min(0.70, float(target_coverage or 0.65)))
    target_seconds = target_coverage * total_duration
    current_coverage_seconds = sum(sp["end_time"] - sp["start_time"] for sp in current_spans)

    import itertools
    cat_cycle = itertools.cycle(available_categories)

    for f_start, f_end in free_intervals:
        if current_coverage_seconds >= target_seconds:
            break
        f_dur = f_end - f_start
        if f_dur < MIN_WINDOW_SECONDS:
            continue

        # 查找落在当前自由区间内的字幕
        f_subs = [
            s for s in subtitles
            if float(s.get("end_time", 0.0)) > f_start + 0.05 and float(s.get("start_time", 0.0)) < f_end - 0.05
        ]

        if f_subs:
            sub_idx = 0
            while sub_idx < len(f_subs) and current_coverage_seconds < target_seconds:
                win_start = max(f_start, float(f_subs[sub_idx].get("start_time", 0.0)))
                cur_idx = sub_idx
                win_end = min(f_end, float(f_subs[cur_idx].get("end_time", 0.0)))

                # 累加后续字幕，直到时长达到 3.0s~5.5s
                while cur_idx + 1 < len(f_subs):
                    next_et = min(f_end, float(f_subs[cur_idx + 1].get("end_time", 0.0)))
                    if (win_end - win_start < 3.0) or (next_et - win_start <= 5.5):
                        cur_idx += 1
                        win_end = next_et
                    else:
                        break

                if win_end - win_start >= MIN_WINDOW_SECONDS:
                    # 若距区间末尾仅剩 < 1.8s（0.x秒快闪），直接延展填满至 f_end
                    if 0 < f_end - win_end < MIN_TALKING_HEAD_SECONDS:
                        win_end = f_end

                    cat = next(cat_cycle)
                    current_spans.append({
                        "start_time": round(win_start, 2),
                        "end_time": round(win_end, 2),
                        "material_category": cat
                    })
                    current_coverage_seconds += (win_end - win_start)

                sub_idx = cur_idx + 1
        else:
            # 无字幕时间戳时的纯时间流调度兜底
            pos = f_start
            while pos + MIN_WINDOW_SECONDS <= f_end and current_coverage_seconds < target_seconds:
                rem = f_end - pos
                win_dur = min(4.5, rem) if rem >= 3.0 else rem
                if win_dur < MIN_WINDOW_SECONDS:
                    break
                win_end = pos + win_dur
                if 0 < f_end - win_end < MIN_TALKING_HEAD_SECONDS:
                    win_end = f_end
                cat = next(cat_cycle)
                current_spans.append({
                    "start_time": round(pos, 2),
                    "end_time": round(win_end, 2),
                    "material_category": cat
                })
                current_coverage_seconds += (win_end - pos)
                pos = win_end

    # 5. 经过 plan_stable_windows 进行近邻合并、时长钳制与覆盖率收敛
    stable_windows = plan_stable_windows(current_spans, total_duration=total_duration)

    # 最终防御：
    # 1. 确保不侵犯开场 1.8s
    # 2. 确保相邻窗口绝对没有 0 < gap < MIN_TALKING_HEAD_SECONDS 的主画面瞬间闪跳
    final_windows = []
    for w in stable_windows:
        if w["start_time"] < 1.8:
            if w["end_time"] > 1.8 + MIN_WINDOW_SECONDS:
                w["start_time"] = 1.8
                final_windows.append(w)
        else:
            final_windows.append(w)

    guarded_windows = []
    for w in final_windows:
        if not guarded_windows:
            guarded_windows.append(w)
            continue
        prev = guarded_windows[-1]
        gap = round(w["start_time"] - prev["end_time"], 3)
        if gap <= 0.05:
            prev["end_time"] = w["start_time"]
            guarded_windows.append(w)
        elif gap < MIN_TALKING_HEAD_SECONDS:
            # 检查 gap 是否落在价格手势或 CTA 禁切区内部
            is_prohibited = any(
                p_st < w["start_time"] and p_et > prev["end_time"]
                for p_st, p_et in prohibited_intervals if p_st > 0.0
            )
            if not is_prohibited:
                prev["end_time"] = w["start_time"]
            guarded_windows.append(w)
        else:
            guarded_windows.append(w)

    return guarded_windows


def validate_and_clip(subtitles: List[Dict[str, Any]], decisions: List[Dict[str, Any]]) -> Dict[str, SceneDecision]:
    """确定性校验与裁剪：逐句产出 SceneDecision（含不切句），全部硬约束在此兜底。"""
    by_id = {str(d.get("id")): d for d in decisions if isinstance(d, dict) and d.get("id")}

    enriched: List[tuple] = []  # (sub, SceneDecision)
    for index, sub in enumerate(subtitles):
        sid = str(sub.get("id"))
        raw = by_id.get(sid, {})
        text = str(sub.get("corrected_text") or sub.get("raw_text") or "")
        sub_start = max(0.0, float(sub.get("start_time", 0.0)))
        duration = max(0.0, float(sub.get("end_time", 0.0)) - sub_start)

        part = _infer_part(index, text, raw.get("part"), start_time=sub_start)
        broll = raw.get("broll")
        broll_cat = MaterialCategory(broll) if broll in VALID_BROLL else None
        reason = str(raw.get("reason") or "")

        # 规则 1/2：不切区强制 null
        is_opening_hook = (part == "hook" and sub_start < 1.8)
        if is_opening_hook or part == "cta" or _is_price_gesture(text):
            if broll_cat is not None:
                reason = (reason + "；已由不切区规则强制裁掉").strip("；")
            broll_cat = None

        if broll_cat is None:
            sd = SceneDecision(part=part, broll_category=None, broll_duration=0.0,
                               transition_seconds=0.0, reason=reason or "保留口播真人画面")
        else:
            try:
                dur = float(raw.get("broll_duration") or 0.0)
            except (TypeError, ValueError):
                dur = 0.0
            if dur <= 0:
                dur = duration * DEFAULT_FALLBACK_RATIO
            dur = min(dur, duration)
            try:
                trans = float(raw.get("transition") or 0.0)
            except (TypeError, ValueError):
                trans = 0.0
            trans = max(0.0, min(0.5, trans))
            sd = SceneDecision(part=part, broll_category=broll_cat, broll_duration=round(dur, 3),
                               transition_seconds=round(trans, 3), reason=reason)
        enriched.append((sub, sd))

    return {str(s.get("id")): sd for s, sd in enriched}


def fallback_keyword_rules(
    subtitles: List[Dict[str, Any]],
    total_duration: float = 0.0,
    target_coverage: float = 0.65
) -> Dict[str, SceneDecision]:
    """降级路径：AI 不可用时按词库关键词规则产出切镜，并由双层编排引擎自适应铺设至 60%~70% 覆盖率"""
    from app.native_engine.keyword_matcher import match_keywords_in_segment

    raw_cues: List[BrollCueItem] = []
    for sub in subtitles:
        text = str(sub.get("corrected_text") or sub.get("raw_text") or "")
        kw = match_keywords_in_segment(text)
        cat_str = kw.get("matched_category")
        if cat_str in VALID_BROLL:
            st = float(sub.get("start_time", 0.0))
            et = float(sub.get("end_time", st))
            raw_cues.append(BrollCueItem(
                start_time=st,
                end_time=et,
                category=MaterialCategory(cat_str),
                visual_intent=f"关键词匹配: {kw.get('matched_keywords', [])}"
            ))

    if total_duration <= 0 and subtitles:
        total_duration = max(float(s.get("end_time", 0.0)) for s in subtitles)

    windows = plan_dual_layer_broll(
        subtitles=subtitles,
        cues=raw_cues,
        total_duration=total_duration,
        target_coverage=target_coverage
    )

    decisions: Dict[str, SceneDecision] = {}
    for idx, sub in enumerate(subtitles):
        sid = str(sub.get("id"))
        st = float(sub.get("start_time", 0.0))
        et = float(sub.get("end_time", st))
        mid = (st + et) / 2.0

        hit_window = None
        for w in windows:
            if w["start_time"] <= mid <= w["end_time"]:
                hit_window = w
                break

        text = str(sub.get("corrected_text") or sub.get("raw_text") or "")
        part = _infer_part(idx, text, declared=None, start_time=st)
        if hit_window and part != "hook" and part != "cta" and not _is_price_gesture(text):
            decisions[sid] = SceneDecision(
                part=part,
                broll_category=hit_window["material_category"],
                broll_duration=round(hit_window["end_time"] - hit_window["start_time"], 2),
                transition_seconds=HARD_CUT_TRANSITION,
                reason="双层编排分镜 (降级保底)"
            )
        else:
            decisions[sid] = SceneDecision(
                part=part,
                broll_category=None,
                broll_duration=0.0,
                transition_seconds=0.0,
                reason="保留口播真人画面"
            )
    return decisions
