"""批量剪辑契约测试（tests/ 内 mock 重型管线，遵循 AGENTS.md 测试边界）。

mock analyze_and_cut / render_project（重量级 ASR/LLM/FFmpeg），验证：
submit 契约、逐项状态流转、单项失败落真实错误且不中断其余、持久化可查询。
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402
from app.models.entities import MaterialCategory, CutProject  # noqa: E402
from app.native_engine.storage import storage_service  # noqa: E402
from app.models.entities import BatchJobItem  # noqa: E402

client = TestClient(app)


def _make_material(tmp_path, name):
    f = tmp_path / name
    f.write_bytes(f"fake_video_stream_{name}".encode())
    return storage_service.save_material(MaterialCategory.TALKING_HEAD, name, f)


def test_submit_validation_errors(tmp_path):
    r = client.post("/api/v1/batch/submit", json={"material_ids": []})
    assert r.status_code == 400
    r2 = client.post("/api/v1/batch/submit", json={"material_ids": ["no-such-id"]})
    assert r2.status_code == 404
    assert "不存在" in r2.json()["detail"]


def test_batch_flow_with_mocked_pipeline(tmp_path, monkeypatch):
    """两项提交：一项成功一项失败（渲染抛错），失败项落真实错误且不中断其余"""
    import app.api.editor as editor_mod

    m_ok = _make_material(tmp_path, "batch_ok.mp4")
    m_bad = _make_material(tmp_path, "batch_bad.mp4")

    async def fake_analyze(req):
        # 模拟坏素材在分析阶段失败
        if req.talking_head_id == m_bad.id:
            raise RuntimeError("ASR 真实失败: 音频流损坏")
        return CutProject(id="proj-ok", title="t", talking_head_id=req.talking_head_id, aspect_ratio=req.aspect_ratio)

    async def fake_render(project_id):
        return CutProject(id=project_id, title="t", talking_head_id="x")

    monkeypatch.setattr(editor_mod, "analyze_and_cut", fake_analyze)
    monkeypatch.setattr(editor_mod, "render_project", fake_render)

    sub = client.post("/api/v1/batch/submit", json={"material_ids": [m_ok.id, m_bad.id], "aspect_ratio": "9:16"})
    assert sub.status_code == 200
    data = sub.json()["data"]
    assert data["queued"] == 2
    assert data["concurrency"] >= 1
    job_id = data["job_id"]

    # BackgroundTasks 在 TestClient 返回前已执行完毕，直接查询最终态
    status = client.get(f"/api/v1/batch/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["status"] == "finished"
    items = {i["material_id"]: i for i in body["items"]}
    assert items[m_ok.id]["status"] == "completed"
    assert items[m_ok.id]["project_id"] == "proj-ok"
    assert items[m_bad.id]["status"] == "failed"
    assert "ASR 真实失败" in items[m_bad.id]["error"], "失败项必须携带真实错误详情"

    # 持久化：任务落库可查询；completed_count 只计真实成功项，失败项单列 failed_count
    # （旧语义把失败项混入 completed_count，导致失败批次被展示成“已完成 5/5”）
    persisted = client.get(f"/api/v1/batch/jobs/{job_id}").json()["data"]
    assert persisted["completed_count"] == 1
    assert persisted["failed_count"] == 1

    listed = client.get("/api/v1/batch/jobs").json()["data"]
    summary = next(j for j in listed if j["job_id"] == job_id)
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 1
