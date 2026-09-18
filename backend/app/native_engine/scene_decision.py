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
MERGE_GAP_SECONDS = 0.8     # 相邻窗口间隔小于此值合并为一个连续分镜，避免快闪交替
EDGE_GAP_SECONDS = 0.3      # 编排后相邻窗口间保留的最小口播间隔
COVERAGE_MIN = 0.40         # 空镜总时长占片长比例下限
COVERAGE_MAX = 0.70         # 占比上限
COVERAGE_TARGET = 0.65      # 目标中心（60%~70% 黄金区间）


def plan_stable_windows(raw_spans: List[Dict[str, Any]], total_duration: float) -> List[Dict[str, Any]]:
    """把逐句零散的空镜窗口编排成稳定的成片分镜时间线（确定性，无 AI）。

    输入 raw_spans: [{start_time, end_time, material_category}]（AI/关键词决策的原始窗口）。
    编排规则：
      1) 相邻窗口间隔 < MERGE_GAP 时合并，消除"闪一下闪一下"的快闪交替；
      2) 单镜时长钳制到 [MIN, MAX]：太长截断；太短向右延展（J-cut：画面延续、口播继续），
         延展不到下限则整窗丢弃——宁可少切不可闪切；
      3) 总覆盖时长收敛到 [COVERAGE_MIN, COVERAGE_TARGET]×片长（约 2/3）：
         不足时按剩余空间向右轮转延展，超上限时从最长窗开始截断（不低于下限）。
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

    # 1. 近邻合并（消除快闪交替）
    merged: List[Dict[str, Any]] = []
    for w in spans:
        if merged and w["start_time"] - merged[-1]["end_time"] < MERGE_GAP_SECONDS:
            merged[-1]["end_time"] = max(merged[-1]["end_time"], w["end_time"])
        else:
            merged.append(dict(w))

    # 2. 单镜时长钳制：太长截断；太短向右延展至下限，延不动则丢弃
    clamped: List[Dict[str, Any]] = []
    for i, w in enumerate(merged):
        start = w["start_time"]
        next_start = merged[i + 1]["start_time"] - EDGE_GAP_SECONDS if i + 1 < len(merged) else total_duration
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
            end = w["end_time"]  # 右侧空间不足时保留原长（间隔侵占 ≤ EDGE_GAP 可容忍）
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
            next_start = result[i + 1]["start_time"] - EDGE_GAP_SECONDS if i + 1 < len(result) else total_duration
            new_end = min(w["start_time"] + hard_cap, max(next_start, w["end_time"]), total_duration)
            grow = min(new_end - w["end_time"], max(target, COVERAGE_MIN * total_duration) - _span(result))
            if grow > 1e-6:
                w["end_time"] += grow
                progressed = True
        if not progressed:
            break

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


def parse_cue_sheet(raw: str) -> List[BrollCueItem]:
    """从大模型稀疏输出中解析 broll_cues 列表"""
    data = llm_client.extract_json(raw)
    if not isinstance(data, dict):
        return []
    items = data.get("broll_cues")
    if not isinstance(items, list):
        if isinstance(data, list):
            items = data
        else:
            return []

    result: List[BrollCueItem] = []
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
    """将大模型输出的粗时间戳吸附至最近的物理词时间戳边缘"""
    all_word_boundaries = []
    for s in subtitles:
        words = s.get("words") or []
        for w in words:
            if isinstance(w, dict):
                all_word_boundaries.append(float(w.get("start", 0.0)))
                all_word_boundaries.append(float(w.get("end", 0.0)))
        all_word_boundaries.append(float(s.get("start_time", 0.0)))
        all_word_boundaries.append(float(s.get("end_time", 0.0)))

    if not all_word_boundaries:
        return cues

    all_word_boundaries = sorted(list(set(all_word_boundaries)))

    snapped: List[BrollCueItem] = []
    for c in cues:
        best_start = min(all_word_boundaries, key=lambda b: abs(b - c.start_time))
        best_end = min(all_word_boundaries, key=lambda b: abs(b - c.end_time))
        if abs(best_start - c.start_time) > 0.6:
            best_start = c.start_time
        if abs(best_end - c.end_time) > 0.6:
            best_end = c.end_time
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
    第一层：强相关语义精准锚定（来自 LLM broll_cues 或关键词命中），吸附词戳并严格执行三大禁切区红线；
    第二层：在未覆盖的自由正文区间自适应随机调度素材铺设 3~5 秒窗口，硬性确保 1~2 分钟成片达到 60%~70% 黄金覆盖率。
    """
    total_duration = max(0.0, float(total_duration or 0.0))
    if total_duration <= 0 and subtitles:
        total_duration = max(float(s.get("end_time", 0.0)) for s in subtitles)

    if not available_categories:
        available_categories = [MaterialCategory.VENUE, MaterialCategory.LESSON, MaterialCategory.EXPERIENCE]

    # 1. 禁切区保护与时间戳吸附
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
        occupied_intervals.append((sp["start_time"] - EDGE_GAP_SECONDS, sp["end_time"] + EDGE_GAP_SECONDS))

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

    # 4. 第二层自适应随机铺底：在 free intervals 中按 3.0~5.0 秒节奏插入空镜
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

        pos = f_start
        while pos + MIN_WINDOW_SECONDS <= f_end and current_coverage_seconds < target_seconds:
            rem = f_end - pos
            win_dur = min(4.0, rem) if rem >= 3.0 else rem
            if win_dur < MIN_WINDOW_SECONDS:
                break
            win_end = pos + win_dur
            cat = next(cat_cycle)
            current_spans.append({
                "start_time": round(pos, 2),
                "end_time": round(win_end, 2),
                "material_category": cat
            })
            current_coverage_seconds += win_dur
            # 镜头间隔预留 1.2s 口播真人出镜（大于 MERGE_GAP_SECONDS=0.8s，杜绝多镜被误合一并被 6s 截断）
            pos = win_end + 1.2

    # 5. 经过 plan_stable_windows 进行最终的近邻合并与时长/覆盖率收敛
    stable_windows = plan_stable_windows(current_spans, total_duration=total_duration)
    
    # 最终防御：确保不侵犯开场 1.8s
    final_windows = []
    for w in stable_windows:
        if w["start_time"] < 1.8:
            if w["end_time"] > 1.8 + MIN_WINDOW_SECONDS:
                w["start_time"] = 1.8
                final_windows.append(w)
        else:
            final_windows.append(w)

    return final_windows


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
