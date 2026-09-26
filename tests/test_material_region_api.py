import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from app.main import app
from app.models.entities import MaterialCategory

client = TestClient(app)

def test_list_zhejiang_regions():
    resp = client.get("/api/v1/materials/regions/zhejiang")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 11
    codes = [item["code"] for item in data]
    assert "浙A·杭州" in codes
    assert "浙E·湖州" in codes


def test_upload_material_with_plate_region(tmp_path):
    # 模拟视频二进制
    file_content = b"fake mp4 video content with sufficient bytes for testing"
    files = {"file": ("test_venue.mp4", file_content, "video/mp4")}
    data = {
        "category": "venue",
        "plate_region": "浙E·湖州"
    }

    resp = client.post("/api/v1/materials/upload", data=data, files=files)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["category"] == "venue"
    assert res_data["plate_region"] == "浙E·湖州"
    mat_id = res_data["id"]

    # 原地修改地区车牌
    patch_resp = client.patch(f"/api/v1/materials/{mat_id}/region", json={"plate_region": "浙A·杭州"})
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()
    assert patch_data["plate_region"] == "浙A·杭州"

    # 按地区筛选
    get_hz = client.get("/api/v1/materials", params={"category": "venue", "plate_region": "浙A·杭州"})
    assert get_hz.status_code == 200
    assert any(m["id"] == mat_id for m in get_hz.json())

    get_other = client.get("/api/v1/materials", params={"category": "venue", "plate_region": "浙B·宁波"})
    assert get_other.status_code == 200
    assert not any(m["id"] == mat_id for m in get_other.json())


def test_import_local_with_plate_region(tmp_path):
    # 创建一个临时本地视频文件
    fake_video = tmp_path / "local_lesson.mp4"
    fake_video.write_bytes(b"local lesson video test content")

    payload = {
        "category": "lesson",
        "file_path": str(fake_video),
        "plate_region": "浙G·金华"
    }
    resp = client.post("/api/v1/materials/import-local", json=payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["category"] == "lesson"
    assert res_data["plate_region"] == "浙G·金华"
