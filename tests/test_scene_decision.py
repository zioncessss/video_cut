"""AI 分镜决策校验器与稳定性编排层单元测试（纯函数，不联网）。

确定性约束分两层：
  validate_and_clip：hook/cta 强制不切；价格手势句强制不切；时长/转场越界裁剪；
  plan_stable_windows（编排层）：近邻合并防闪、单镜 2~6s 钳制、总覆盖收敛 [40%,70%] 目标 60%。
固件：用户真实口播文本 tests/fixtures/。
"""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.scene_decision import (  # noqa: E402
    parse_decisions,
    validate_and_clip,
    fallback_keyword_rules,
    load_fixture_subtitles,
    plan_stable_windows,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _xiaoshan_subs():
    return load_fixture_subtitles(FIXTURES / "xiaoshan_price.txt")


def test_fixture_loads():
    subs = _xiaoshan_subs()
    assert len(subs) == 7
    assert subs[0]["id"] == "v2-1"
    assert "不要这个数" in subs[4]["corrected_text"]


def test_hook_and_cta_forced_null():
    subs = _xiaoshan_subs()
    decisions = [
        {"id": "v2-1", "part": "hook", "broll": "venue", "broll_duration": 1.0, "transition": 0.4, "reason": "AI误判开场"},
        {"id": "v2-7", "part": "cta", "broll": "lesson", "broll_duration": 2.0, "transition": 0.4, "reason": "AI误判CTA"},
    ]
    result = validate_and_clip(subs, decisions)
    assert result["v2-1"].broll_category is None, "hook 句必须强制不切"
    assert result["v2-7"].broll_category is None, "cta 句必须强制不切"


def test_price_gesture_sentence_forced_null():
    subs = _xiaoshan_subs()
    # AI 把手势报价句误判为 venue，校验器必须裁掉
    decisions = [{"id": "v2-5", "part": "body", "broll": "venue", "broll_duration": 5.0, "transition": 0.4, "reason": "误判"}]
    result = validate_and_clip(subs, decisions)
    assert result["v2-5"].broll_category is None, "价格手势句（不要这个数/只要这个数）必须强制不切"


def test_duration_and_transition_clipped():
    subs = _xiaoshan_subs()
    v3 = next(s for s in subs if s["id"] == "v2-3")  # 6.0 ~ 12.5，句长 6.5s
    decisions = [
        {"id": "v2-3", "part": "body", "broll": "experience", "broll_duration": 99.0, "transition": 2.0, "reason": "超界"},
    ]
    result = validate_and_clip(subs, decisions)
    sd = result["v2-3"]
    assert sd.broll_category is not None
    assert sd.broll_duration <= (v3["end_time"] - v3["start_time"]), "空镜时长不得超过句长"
    assert 0 <= sd.transition_seconds <= 0.5, "转场必须落在 [0, 0.5]"


def test_adjacent_candidates_survive_validation_for_planner_merge():
    """相邻切镜不再在校验层裁掉：交给编排层合并为一个连续分镜（防闪）"""
    subs = _xiaoshan_subs()
    # v2-3(6.0-12.5) 与 v2-4(13.0-15.5) 相邻：两者都保留，由编排层合并
    decisions = [
        {"id": "v2-3", "part": "body", "broll": "experience", "broll_duration": 3.0, "transition": 0.4, "reason": "a"},
        {"id": "v2-4", "part": "body", "broll": "experience", "broll_duration": 2.0, "transition": 0.4, "reason": "b"},
    ]
    result = validate_and_clip(subs, decisions)
    assert result["v2-3"].broll_category is not None
    assert result["v2-4"].broll_category is not None, "相邻切镜保留给编排层合并，不再在校验层裁掉"


def test_plan_stable_windows_merges_flash_cuts():
    """编排层：0.4s 间隔的快闪窗口必须合并为一个连续分镜；
    合并后若覆盖率仍低于 40% 下限，允许延展到硬上限 10s（连续镜头不闪切）"""
    raw = [
        {"start_time": 3.0, "end_time": 4.0, "material_category": "venue"},
        {"start_time": 4.4, "end_time": 5.6, "material_category": "venue"},
    ]
    planned = plan_stable_windows(raw, total_duration=27.0)
    assert len(planned) == 1, "间隔 0.4s 的两个窗口必须合并"
    w = planned[0]
    assert w["end_time"] - w["start_time"] >= 2.0, "合并后不得低于频闪下限"
    assert w["end_time"] - w["start_time"] <= 10.0, "覆盖率补足延展也不得超过硬上限"


def test_plan_stable_windows_extends_short_window_and_drops_unfixable():
    """短窗向右延展到 2s 下限；无处延展的极短窗丢弃（宁可少切不可闪切）"""
    raw = [
        {"start_time": 5.0, "end_time": 5.8, "material_category": "venue"},   # 右侧空间充足 → 延展到 2s
        {"start_time": 26.5, "end_time": 26.9, "material_category": "venue"}, # 已到片尾(27s) → 丢弃
    ]
    planned = plan_stable_windows(raw, total_duration=27.0)
    assert len(planned) == 1
    w = planned[0]
    assert abs(w["start_time"] - 5.0) < 1e-6
    assert w["end_time"] - w["start_time"] >= 2.0


def test_plan_stable_windows_truncates_long_window():
    """9s 单窗在 30s 片长中占比 30% 低于 40% 下限：允许延展到硬上限 10s 补覆盖，
    但绝不允许超过硬上限；若 AI 决策密集（覆盖率已达标）则仍按 6s 截断"""
    raw = [{"start_time": 4.0, "end_time": 13.0, "material_category": "lesson"}]
    planned = plan_stable_windows(raw, total_duration=30.0)
    assert len(planned) == 1
    dur = planned[0]["end_time"] - planned[0]["start_time"]
    assert 6.0 <= dur <= 10.0, f"覆盖率补足延展应落在 [6,10]，实际 {dur}"


def test_plan_stable_windows_truncates_when_coverage_adequate():
    """覆盖率已达标时（两窗合计 ≥40%），单镜仍按 6s 软上限截断"""
    raw = [
        {"start_time": 2.0, "end_time": 8.0, "material_category": "lesson"},   # 6s
        {"start_time": 14.0, "end_time": 20.0, "material_category": "venue"},  # 6s，合计 12s/30s=40%
    ]
    planned = plan_stable_windows(raw, total_duration=30.0)
    for w in planned:
        dur = w["end_time"] - w["start_time"]
        assert dur <= 6.0 + 1e-6, f"覆盖率达标时单镜按 6s 截断，实际 {dur}"


def test_plan_stable_windows_coverage_band():
    """覆盖率收敛：分散短窗应被延展进 [40%, 70%] 覆盖带；超量的长窗被截回带内"""
    # 30s 片长，三个分散的 1.5s 短窗（间隔充足不合并）
    raw = [
        {"start_time": 3.0, "end_time": 4.5, "material_category": "venue"},
        {"start_time": 12.0, "end_time": 13.5, "material_category": "experience"},
        {"start_time": 21.0, "end_time": 22.5, "material_category": "lesson"},
    ]
    planned = plan_stable_windows(raw, total_duration=30.0)
    total = sum(w["end_time"] - w["start_time"] for w in planned)
    assert 0.40 * 30 - 1e-6 <= total <= 0.70 * 30 + 1e-6, f"覆盖率应收敛到 [40%,70%]，实际 {total/30:.0%}"
    for w in planned:
        assert 2.0 <= w["end_time"] - w["start_time"] <= 6.0 + 1e-6

    # 反向：超量长窗被截回带内
    raw_over = [{"start_time": 2.0, "end_time": 29.0, "material_category": "lesson"}]
    planned_over = plan_stable_windows(raw_over, total_duration=30.0)
    total_over = sum(w["end_time"] - w["start_time"] for w in planned_over)
    assert total_over <= 0.70 * 30 + 1e-6, f"覆盖率不得超上限，实际 {total_over/30:.0%}"


def test_parse_decisions_tolerates_markdown_wrapped_json():
    raw = '好的，以下是决策：\n```json\n{"decisions": [{"id": "v2-1", "part": "hook", "broll": null, "broll_duration": 0, "transition": 0, "reason": "开场"}]}\n```'
    decisions = parse_decisions(raw)
    assert decisions and decisions[0]["id"] == "v2-1"


def test_fallback_keyword_rules_produce_cuts_and_respect_rules():
    """降级路径：关键词规则也能产出切镜，且同样通过全部确定性约束"""
    subs = _xiaoshan_subs()
    result = fallback_keyword_rules(subs)
    # v2-3 含「场地/试学/体验」词库词 → 应命中切镜；hook/cta/手势句必须为空
    assert result["v2-3"].broll_category is not None, "含词库关键词的句子降级时也应切镜"
    assert result["v2-1"].broll_category is None
    assert result["v2-5"].broll_category is None
    assert result["v2-7"].broll_category is None


def test_opening_broll_after_2s_allowed():
    """开场 2s 后如果出现场地或校区词，允许切入分镜，解除前置过度防切"""
    subs = [
        {"id": "s1", "start_time": 0.0, "end_time": 1.5, "corrected_text": "同学们好"}, # < 1.8s, hook
        {"id": "s2", "start_time": 2.2, "end_time": 5.5, "corrected_text": "在湖州学个驾校真的没有你们想的那么复杂"}, # >= 1.8s, venue
        {"id": "s3", "start_time": 6.0, "end_time": 8.5, "corrected_text": "我们在安吉这边呢训练场很大"}, # venue
    ]
    decisions = [
        {"id": "s1", "part": "hook", "broll": "venue", "broll_duration": 1.0, "transition": 0.3, "reason": "开场误切"},
        {"id": "s2", "part": "body", "broll": "venue", "broll_duration": 2.5, "transition": 0.3, "reason": "提到湖州驾校"},
        {"id": "s3", "part": "body", "broll": "venue", "broll_duration": 2.5, "transition": 0.3, "reason": "提到安吉场地"},
    ]
    result = validate_and_clip(subs, decisions)
    assert result["s1"].broll_category is None, "0~1.5s 开场钩子必须保持真人出镜"
    assert result["s2"].broll_category is not None, "2s 后提到湖州驾校应允许切入场地空镜"
    assert result["s3"].broll_category is not None, "后续提到安吉训练场应允许切入场地空镜"
