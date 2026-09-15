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
    assert "active_harness" in res.json()

    post_res = client.post(
        "/api/v1/settings",
        json={"active_harness": "embedded", "llm_model": "gpt-4o-mini"}
    )
    assert post_res.status_code == 200
    assert post_res.json()["data"]["active_harness"] == "embedded"

def test_batch_api():
    res = client.post(
        "/api/v1/batch/jobs",
        json={"total_count": 2, "concurrency_limit": 2}
    )
    assert res.status_code == 200
    job_id = res.json()["id"]

    list_res = client.get("/api/v1/batch/jobs")
    assert list_res.status_code == 200
    assert any(j["id"] == job_id for j in list_res.json())
