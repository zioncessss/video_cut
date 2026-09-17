"""AI 分镜决策：解析、确定性校验裁剪（双保险）与关键词规则降级。

设计依据 specs/005-auto-edit-pipeline/research.md R8（真实口播风格模型）：
四类硬性不切区（开场钩子/价格手势句/结尾CTA/情绪叙事）+ 节奏约束（不相邻连续切、占比≤40%）。
AI 输出永不直接信任，必须经过 validate_and_clip 的确定性约束。
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


def _infer_part(index: int, text: str, declared: Optional[str]) -> str:
    """part 推断：首句恒为 hook；CTA 话术正则兜底；其余尊重 AI 声明"""
    if index == 0:
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
        duration = max(0.0, float(sub.get("end_time", 0.0)) - float(sub.get("start_time", 0.0)))

        part = _infer_part(index, text, raw.get("part"))
        broll = raw.get("broll")
        broll_cat = MaterialCategory(broll) if broll in VALID_BROLL else None
        reason = str(raw.get("reason") or "")

        # 规则 1/2：不切区强制 null（AI 误判也裁）
        if part in ("hook", "cta") or _is_price_gesture(text):
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

    # 规则 5：不相邻连续切——相邻两句均切时裁掉后句
    for i in range(1, len(enriched)):
        prev_sd = enriched[i - 1][1]
        cur_sub, cur_sd = enriched[i]
        if prev_sd.broll_category is not None and cur_sd.broll_category is not None:
            cur_sd.broll_category = None
            cur_sd.broll_duration = 0.0
            cur_sd.reason = (cur_sd.reason + "；已由相邻间隔规则裁掉").strip("；")

    # 规则 6：全片空镜占比 ≤ 40%，超限按单处时长从大到小依次裁
    total = sum(max(0.0, float(s.get("end_time", 0.0)) - float(s.get("start_time", 0.0))) for s, _ in enriched)
    if total > 0:
        kept = [(s, sd) for s, sd in enriched if sd.broll_category is not None]
        ratio = sum(sd.broll_duration for _, sd in kept) / total
        while kept and ratio > MAX_BROLL_RATIO:
            largest = max(kept, key=lambda pair: pair[1].broll_duration)
            largest[1].broll_category = None
            largest[1].reason = (largest[1].reason + "；已由占比上限规则裁掉").strip("；")
            kept.remove(largest)
            ratio = sum(sd.broll_duration for _, sd in kept) / total

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
