import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app

client = TestClient(app)

def test_system_and_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_sys = client.get("/api/v1/system/resources")
    assert res_sys.status_code == 200
    data = res_sys.json()
    assert "cpu_cores" in data
    assert "memory_available_gb" in data
    assert "recommended_concurrency" in data

def test_settings_api():
    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    orig_settings = res.json()
    assert "active_harness" in orig_settings

    try:
        post_res = client.post(
            "/api/v1/settings",
            json={"active_harness": "embedded", "llm_model": "glm-5.3-flash"}
        )
        assert post_res.status_code == 200
        assert post_res.json()["data"]["active_harness"] == "embedded"

        probe_res = client.post(
            "/api/v1/settings/test-harness",
            json={"engine": "embedded"}
        )
        assert probe_res.status_code == 200
        probe_data = probe_res.json()
        assert probe_data["code"] == 0
        assert probe_data["data"]["success"] is True
    finally:
        # 恢复原始 settings，防止单测污染生产配置
        client.post("/api/v1/settings", json={
            "active_harness": orig_settings.get("active_harness", "codex"),
            "llm_model": orig_settings.get("llm_model", "glm-5.3-flash")
        })


def test_batch_api():
    """批量剪辑契约（005）：submit 校验 + 任务列表持久化"""
    # 旧模拟端点已移除，submit 必须校验素材存在性
    res = client.post(
        "/api/v1/batch/submit",
        json={"material_ids": [], "aspect_ratio": "9:16"}
    )
    assert res.status_code == 400
    res_missing = client.post(
        "/api/v1/batch/submit",
        json={"material_ids": ["no-such-material"], "aspect_ratio": "9:16"}
    )
    assert res_missing.status_code == 404

    list_res = client.get("/api/v1/batch/jobs")
    assert list_res.status_code == 200
    assert isinstance(list_res.json()["data"], list)


def test_pipeline_e2e_flow():
    """全自动剪辑流水线端到端验证：ASR意群断句（无腰斩）与双层 60%~70% 分镜编排"""
    from app.native_engine.asr_runner import asr_runner
    from app.native_engine.scene_decision import plan_dual_layer_broll, BrollCueItem
    from app.models.entities import MaterialCategory

    # 1. 模拟 60 秒口播音频识别出的逐字 segments (含标点及设问长句)
    sample_stt = {
        "text": "从今年九月份开始，杭州驾校迎来了大改革。千万不要报。我是小陈，在杭州教车八年。就知道现在很多踩坑的原因是什么。全包只要这个数绝不加钱。我们自建五万平训练场，专业金牌教练带教，科目二倒库轻松一把过。想要学车的朋友记得评论区找我聊。",
        "duration": 60.0,
        "segments": [
            {"id": 0, "start": 0.5, "end": 2.0, "text": "从今年九月份开始，"},
            {"id": 1, "start": 2.1, "end": 4.5, "text": "杭州驾校迎来了大改革。"},
            {"id": 2, "start": 4.8, "end": 6.2, "text": "千万不要报。"},
            {"id": 3, "start": 6.5, "end": 9.5, "text": "我是小陈，在杭州教车八年。"},
            {"id": 4, "start": 9.8, "end": 13.5, "text": "就知道现在很多踩坑的原因是什么。"},
            {"id": 5, "start": 13.8, "end": 16.5, "text": "全包只要这个数绝不加钱。"},
            {"id": 6, "start": 17.0, "end": 23.0, "text": "我们自建五万平训练场，专业金牌教练带教，"},
            {"id": 7, "start": 23.5, "end": 35.0, "text": "科目二倒库轻松一把过。"},
            {"id": 8, "start": 35.5, "end": 55.0, "text": "场地车接车送，体检十分钟搞定。"},
            {"id": 9, "start": 55.5, "end": 59.5, "text": "想要学车的朋友记得评论区找我聊。"}
        ]
    }

    raw_segments = asr_runner.parse_minimax_response(sample_stt)
    chunked = asr_runner.split_into_readable_segments(raw_segments, max_chars=18)

    # 验证字数均在 8~18 字健康区间，且无大于 18 字的臃肿长句
    assert len(chunked) >= 5
    for seg in chunked:
        assert len(seg["raw_text"]) <= 18, f"字幕句超长: {seg['raw_text']}"
        # 验证物理词中没有残留标点
        for w in seg.get("words", []):
            assert not any(p in w["word"] for p in "，。？！,!?")

    # 2. 模拟 LLM 返回的稀疏强相关 cue (场地 venue)
    cues = [
        BrollCueItem(start_time=17.0, end_time=22.0, category=MaterialCategory.VENUE, visual_intent="自建五万平训练场实景")
    ]

    # 3. 触发双层编排，目标 65% (0.60 ~ 0.70)
    windows = plan_dual_layer_broll(
        subtitles=chunked,
        cues=cues,
        total_duration=60.0,
        target_coverage=0.65,
        available_categories=[MaterialCategory.VENUE, MaterialCategory.LESSON, MaterialCategory.EXPERIENCE]
    )

    total_broll = sum(w["end_time"] - w["start_time"] for w in windows)
    cov = total_broll / 60.0

    assert 0.58 <= cov <= 0.72, f"成片空镜覆盖率未达 60%~70%: {cov:.1%}"
    assert not any(w["start_time"] < 1.8 for w in windows), "前 1.8s 开场保护失效"
    # 验证手势报价句（13.8~16.5s）未被覆盖
    for w in windows:
        overlap = max(0.0, min(w["end_time"], 16.5) - max(w["start_time"], 13.8))
        assert overlap <= 0.3, "报价手势句未受保护"
