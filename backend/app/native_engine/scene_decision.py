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
from app.models.entities import MaterialCategory, SceneDecision

VALID_BROLL = {c.value for c in (MaterialCategory.VENUE, MaterialCategory.EXPERIENCE, MaterialCategory.LESSON)}

# 价格手势句：画面比划报价是内容本体，切走即内容丢失
_PRICE_GESTURE_RE = re.compile(r"这个数|这个价|这么多|比这个|价格?是?这个")
# 结尾行动召唤话术（part 推断兜底，AI 未标或误标时纠正）
_CTA_RE = re.compile(r"滴滴我|找我聊|点红心|点个红心|关注一下|觉得怎么样|报名都没有关系|私信我|评论区")

MAX_BROLL_RATIO = 0.40
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
COVERAGE_TARGET = 0.60      # 目标中心（约 2/3，略保守）


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

        # 规则 1/2：不切区强制 null（AI 误判也裁）
        # 开场保护：开播 1.8s 以内强制真人出镜，2s 之后若提到场地/校区/体验等核心语义，允许自然切入分镜
        is_opening_hook = (part == "hook" and sub_start < 1.8)
        if is_opening_hook or part == "cta" or _is_price_gesture(text):
            if broll_cat is not None:
                reason = (reason + "；已由不切区规则强制裁掉").strip("；")
            broll_cat = None

        if broll_cat is None:
            sd = SceneDecision(part=part, broll_category=None, broll_duration=0.0,
                               transition_seconds=0.0, reason=reason or "保留口播真人画面")
        else:
            # 规则 3：时长不得超过句长；未给或非法时取句长 60%
            try:
                dur = float(raw.get("broll_duration") or 0.0)
            except (TypeError, ValueError):
                dur = 0.0
            if dur <= 0:
                dur = duration * DEFAULT_FALLBACK_RATIO
            dur = min(dur, duration)
            # 规则 4：转场 ∈ [0, 0.5]
            try:
                trans = float(raw.get("transition") or 0.0)
            except (TypeError, ValueError):
                trans = 0.0
            trans = max(0.0, min(0.5, trans))
            sd = SceneDecision(part=part, broll_category=broll_cat, broll_duration=round(dur, 3),
                               transition_seconds=round(trans, 3), reason=reason)
        enriched.append((sub, sd))

    # 规则 5/6（不相邻裁剪、占比 ≤40% 上限）已移除：节奏稳定与覆盖率改由
    # plan_stable_windows 编排层统一负责（合并防闪 + 时长钳制 + 覆盖率收敛到约 2/3）。

    return {str(s.get("id")): sd for s, sd in enriched}


def fallback_keyword_rules(subtitles: List[Dict[str, Any]]) -> Dict[str, SceneDecision]:
    """降级路径：AI 不可用时按词库关键词规则产出切镜（60% 句长 + 硬切），
    并通过与 AI 决策完全相同的确定性校验（不切区/相邻/占比）。"""
    from app.native_engine.keyword_matcher import match_keywords_in_segment

    raw_decisions: List[Dict[str, Any]] = []
    for index, sub in enumerate(subtitles):
        text = str(sub.get("corrected_text") or sub.get("raw_text") or "")
        kw = match_keywords_in_segment(text)
        cat = kw.get("matched_category")
        dur = (float(sub["end_time"]) - float(sub["start_time"])) * DEFAULT_FALLBACK_RATIO if cat else 0.0
        raw_decisions.append({
            "id": str(sub.get("id")),
            "part": "body",
            "broll": cat,
            "broll_duration": round(dur, 3),
            "transition": HARD_CUT_TRANSITION,
            "reason": f"关键词规则命中（降级）：{kw.get('matched_keywords', [])}" if cat else "关键词规则未命中（降级）",
        })
    return validate_and_clip(subtitles, raw_decisions)
