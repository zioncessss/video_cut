import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory, PipelineStage
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.api.editor import _pipeline_progress

client = TestClient(app)

def test_editor_pipeline_progress_dual_key_and_fallback(tmp_path):
    # 1. 准备测试口播素材
    fake_th_file = tmp_path / "th_prog.mp4"
    fake_th_file.write_bytes(b"fake_talking_head_video_for_progress")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_prog.mp4", fake_th_file)

    try:
        # 初始状态查询：应返回 idle (0%)
        res_init = client.get(f"/api/v1/projects/{th.id}/progress")
        assert res_init.status_code == 200
        data_init = res_init.json()
        assert data_init["stage"] == PipelineStage.IDLE.value
        assert data_init["percent"] == 0

        # 执行 analyze-and-cut
        res_cut = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={
                "talking_head_id": th.id,
                "aspect_ratio": "9:16",
                "auto_broll": False,
                "enable_scene_decision": False,
                "auto_render": False,
            }
        )
        assert res_cut.status_code == 200
        proj_data = res_cut.json()
        proj_id = proj_data["id"]

        # 断言双键更新：既可以通过 talking_head_id 查询到 completed (100%)，也可以通过 project.id 查询到
        res_prog_th = client.get(f"/api/v1/projects/{th.id}/progress")
        assert res_prog_th.status_code == 200
        assert res_prog_th.json()["stage"] == PipelineStage.COMPLETED.value
        assert res_prog_th.json()["percent"] == 100

        res_prog_proj = client.get(f"/api/v1/projects/{proj_id}/progress")
        assert res_prog_proj.status_code == 200
        assert res_prog_proj.json()["stage"] == PipelineStage.COMPLETED.value
        assert res_prog_proj.json()["percent"] == 100

        # 测试跨键回退查询能力：若从字典临时移除 proj_id，通过 project_storage_service 关联查询依然能命中 talking_head_id 进度
        cached_proj_prog = _pipeline_progress.pop(proj_id, None)
        try:
            res_fallback = client.get(f"/api/v1/projects/{proj_id}/progress")
            assert res_fallback.status_code == 200
            assert res_fallback.json()["stage"] == PipelineStage.COMPLETED.value
            assert res_fallback.json()["percent"] == 100
        finally:
            if cached_proj_prog:
                _pipeline_progress[proj_id] = cached_proj_prog

    finally:
        storage_service.delete_material(th.id)
