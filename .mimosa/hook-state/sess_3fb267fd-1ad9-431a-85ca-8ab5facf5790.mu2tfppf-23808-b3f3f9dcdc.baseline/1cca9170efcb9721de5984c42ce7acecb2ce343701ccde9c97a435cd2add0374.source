import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory

client = TestClient(app)

def test_material_api_flow():
    # 上传测试
    file_content = b"fake_mp4_bytes_stream"
    response = client.post(
        "/api/v1/materials/upload",
        data={"category": "venue"},
        files={"file": ("site_test.mp4", file_content, "video/mp4")}
    )
    assert response.status_code == 200
    data = response.json()
    material_id = data["id"]
    assert data["category"] == "venue"
    assert data["filename"] == "site_test.mp4"

    # 查询列表
    list_res = client.get("/api/v1/materials?category=venue")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(item["id"] == material_id for item in items)

    # 删除测试
    del_res = client.delete(f"/api/v1/materials/{material_id}")
    assert del_res.status_code == 200

    # 再次查询应不存在
    get_res = client.get(f"/api/v1/materials/{material_id}")
    assert get_res.status_code == 404
