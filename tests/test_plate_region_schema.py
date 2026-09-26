import pytest
import uuid
import time
from app.core.plate_regions import (
    ZHEJIANG_REGIONS,
    REGION_CODES,
    is_valid_zhejiang_region,
    normalize_region_code,
    deduce_target_region,
    DEFAULT_REGION_CODE
)
from app.models.entities import Material, MaterialCategory, CutProject
from app.db.repository import MaterialRepository, ProjectRepository
from app.db.session import get_db_connection


def test_plate_regions_constants():
    assert len(ZHEJIANG_REGIONS) == 11
    assert "浙A·杭州" in REGION_CODES
    assert "浙E·湖州" in REGION_CODES
    assert is_valid_zhejiang_region("浙A·杭州")
    assert is_valid_zhejiang_region("浙E·湖州")
    assert not is_valid_zhejiang_region("苏A·南京")
    assert not is_valid_zhejiang_region(None)

    assert normalize_region_code("浙A") == "浙A·杭州"
    assert normalize_region_code("杭州") == "浙A·杭州"
    assert normalize_region_code("浙E·湖州") == "浙E·湖州"
    assert normalize_region_code("未知") is None


def test_material_repository_plate_region(tmp_path):
    repo = MaterialRepository()
    mat_id = str(uuid.uuid4())
    mat = Material(
        id=mat_id,
        category=MaterialCategory.VENUE,
        filename="test_venue.mp4",
        filepath="storage/materials/venue/test_venue.mp4",
        duration=10.0,
        plate_region="浙E·湖州"
    )
    saved = repo.save(mat)
    assert saved.plate_region == "浙E·湖州"

    loaded = repo.get_by_id(mat_id)
    assert loaded is not None
    assert loaded.plate_region == "浙E·湖州"

    # 更新 plate_region
    ok = repo.update_plate_region(mat_id, "浙A·杭州")
    assert ok is True
    reloaded = repo.get_by_id(mat_id)
    assert reloaded.plate_region == "浙A·杭州"

    # 按 plate_region 过滤查询
    mats_hz = repo.list_all(category=MaterialCategory.VENUE, plate_region="浙A·杭州")
    assert any(m.id == mat_id for m in mats_hz)

    mats_other = repo.list_all(category=MaterialCategory.VENUE, plate_region="浙B·宁波")
    assert not any(m.id == mat_id for m in mats_other)


def test_project_repository_target_region():
    mat_repo = MaterialRepository()
    th_id = str(uuid.uuid4())
    mat_repo.save(Material(
        id=th_id,
        category=MaterialCategory.TALKING_HEAD,
        filename="th.mp4",
        filepath="storage/materials/talking_head/th.mp4"
    ))

    proj_repo = ProjectRepository()
    proj_id = str(uuid.uuid4())
    proj = CutProject(
        id=proj_id,
        title="湖州学车视频",
        talking_head_id=th_id,
        target_region="浙E·湖州"
    )
    proj_repo.save(proj)

    loaded = proj_repo.get_by_id(proj_id)
    assert loaded is not None
    assert loaded.target_region == "浙E·湖州"
