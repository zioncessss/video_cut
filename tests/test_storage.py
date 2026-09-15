import pytest
import sys
from pathlib import Path

# 将 backend 加入 sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models.entities import MaterialCategory
from app.native_engine.storage import storage_service

def test_save_and_list_material(tmp_path):
    # 创建一个伪造的测试视频文件
    fake_video = tmp_path / "test_site.mp4"
    fake_video.write_bytes(b"fake_video_content_for_testing")

    material = storage_service.save_material(
        category=MaterialCategory.VENUE,
        filename="test_site.mp4",
        source_path_or_bytes=fake_video
    )

    assert material.id is not None
    assert material.category == MaterialCategory.VENUE
    assert material.filename == "test_site.mp4"
    assert "storage/materials/venue" in material.filepath

    # 验证列表读取
    venue_materials = storage_service.list_materials(category=MaterialCategory.VENUE)
    assert any(m.id == material.id for m in venue_materials)

    # 验证按 ID 获取
    retrieved = storage_service.get_material(material.id)
    assert retrieved is not None
    assert retrieved.id == material.id

    # 清理
    storage_service.delete_material(material.id)
    assert storage_service.get_material(material.id) is None
