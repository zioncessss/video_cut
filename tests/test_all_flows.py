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
