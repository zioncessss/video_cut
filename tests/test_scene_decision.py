"""AI 分镜决策校验器单元测试（纯函数，不联网）。

六大确定性行为（research.md R8 双保险后端侧）：
  1. part=hook/cta 强制不切；2. 价格手势句强制不切（AI 误判也裁）；
  3. broll_duration 越界裁剪；4. transition 越界 [0,0.5] 裁剪；
  5. 不相邻连续切；6. 全片空镜占比 ≤40%。
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


def test_adjacent_cuts_second_removed():
    subs = _xiaoshan_subs()
    # v2-3(6.0-12.5) 与 v2-4(13.0-15.5) 相邻：两者都切时第二句必须被裁
    decisions = [
        {"id": "v2-3", "part": "body", "broll": "experience", "broll_duration": 3.0, "transition": 0.4, "reason": "a"},
        {"id": "v2-4", "part": "body", "broll": "experience", "broll_duration": 2.0, "transition": 0.4, "reason": "b"},
    ]
    result = validate_and_clip(subs, decisions)
    assert result["v2-3"].broll_category is not None
    assert result["v2-4"].broll_category is None, "不相邻规则：连续两句只保留第一处切镜"


def test_total_broll_ratio_capped_at_40pct():
    subs = load_fixture_subtitles(FIXTURES / "hangzhou_story.txt")
    # 构造 11 句中 8 句切镜 → 占比远超 40%，校验器必须裁至达标
    decisions = []
    for s in subs[:8]:
        decisions.append({
            "id": s["id"], "part": "body",
            "broll": "lesson", "broll_duration": (s["end_time"] - s["start_time"]) * 0.9,
            "transition": 0.4, "reason": "压测占比",
        })
    result = validate_and_clip(subs, decisions)
    total = sum(s["end_time"] - s["start_time"] for s in subs)
    kept = [sd for sd in result.values() if sd.broll_category is not None]
    ratio = sum(sd.broll_duration for sd in kept) / total
    assert ratio <= 0.40 + 1e-6, f"空镜占比必须 ≤40%，实际 {ratio:.0%}"
    assert len(kept) < 8, "超限时应按时长从大到小裁掉部分切镜"


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
