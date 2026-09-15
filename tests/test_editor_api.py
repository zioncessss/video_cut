import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory
from app.native_engine.storage import storage_service

client = TestClient(app)

def test_editor_analyze_and_render_flow(tmp_path):
    # 1. 创建并保存一个口播视频素材和一个场地视频素材
    fake_th_file = tmp_path / "talking_head.mp4"
    fake_th_file.write_bytes(b"fake_talking_head_video_stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "talking_head.mp4", fake_th_file)

    fake_venue_file = tmp_path / "venue.mp4"
    fake_venue_file.write_bytes(b"fake_venue_video_stream")
    venue = storage_service.save_material(MaterialCategory.VENUE, "venue.mp4", fake_venue_file)

    # 2. 调用 /analyze-and-cut
    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": True}
    )
    assert res.status_code == 200
    proj_data = res.json()
    project_id = proj_data["id"]
    assert len(proj_data["subtitles"]) > 0
    assert proj_data["status"] == "draft"

    # 3. 验证字幕修改
    subtitles = proj_data["subtitles"]
    subtitles[0]["corrected_text"] = "修改后的第一句字幕"
    put_res = client.put(
        f"/api/v1/projects/{project_id}/subtitles",
        json={"subtitles": subtitles}
    )
    assert put_res.status_code == 200
    assert put_res.json()["subtitles"][0]["corrected_text"] == "修改后的第一句字幕"

    # 4. 调用渲染
    render_res = client.post(f"/api/v1/projects/{project_id}/render")
    assert render_res.status_code == 200
    render_data = render_res.json()
    assert render_data["status"] == "completed"
    assert render_data["output_video_path"] is not None

    # 清理
    storage_service.delete_material(th.id)
    storage_service.delete_material(venue.id)
