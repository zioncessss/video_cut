"""素材查重与清理机制专项测试：
1. 验证同分类基于 SHA-256 查重复用（0冗余写盘与0重复入库）
2. 验证跨分类复用同一底层物理文件
3. 验证孤儿文件与测试垃圾文件（batch_bad_* 等）的安全检测与自动清除
4. 验证存量重复素材合并时，被工程引用的记录作为权威素材，工程 talking_head_id 无损重定向
5. 验证 POST /api/v1/materials/cleanup 维护接口契约
"""
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import CATEGORY_DIRS, STORAGE_DIR
from app.models.entities import MaterialCategory, CutProject
from app.native_engine.storage import StorageService
from app.db.repository import MaterialRepository, ProjectRepository
from app.db.session import get_db_connection

client = TestClient(app)


def test_material_save_deduplication_same_category(tmp_path):
    storage = StorageService()
    content = b"unique_video_content_for_dedup_test_1"
    
    # 第一次保存
    mat1 = storage.save_material(MaterialCategory.TALKING_HEAD, "person1.mp4", content)
    assert mat1.content_hash is not None
    assert mat1.file_size == len(content)

    # 第二次保存相同内容，文件名不同
    mat2 = storage.save_material(MaterialCategory.TALKING_HEAD, "person1_copy.mp4", content)
    
    # 同分类查重：直接复用同一实体与同一物理路径
    assert mat1.id == mat2.id
    assert mat1.filepath == mat2.filepath

    # 磁盘上只有一份确定性命名物理文件
    disk_path = (STORAGE_DIR.parent / mat1.filepath).resolve()
    assert disk_path.exists()
    assert f"_{mat1.content_hash[:12]}" in disk_path.name


def test_material_save_cross_category_shares_disk_file():
    storage = StorageService()
    content = b"shared_broll_content_across_categories"

    mat_venue = storage.save_material(MaterialCategory.VENUE, "venue_cam.mp4", content)
    mat_exp = storage.save_material(MaterialCategory.EXPERIENCE, "exp_cam.mp4", content)

    # 跨分类：记录不同，但复用相同的物理底层文件
    assert mat_venue.id != mat_exp.id
    assert mat_venue.category == MaterialCategory.VENUE
    assert mat_exp.category == MaterialCategory.EXPERIENCE
    assert mat_venue.filepath == mat_exp.filepath
    assert mat_venue.content_hash == mat_exp.content_hash


def test_cleanup_orphan_and_test_junk():
    storage = StorageService()
    talking_head_dir = CATEGORY_DIRS["talking_head"]
    talking_head_dir.mkdir(parents=True, exist_ok=True)

    # 构造测试垃圾文件与未登记的孤儿文件
    junk_file = talking_head_dir / "batch_bad_fake_sample.mp4"
    junk_file.write_bytes(b"dummy_junk_123")
    orphan_file = talking_head_dir / "orphan_abandoned_video.mp4"
    orphan_file.write_bytes(b"dummy_orphan_456")

    assert junk_file.exists()
    assert orphan_file.exists()

    # 1. 试运行 (dry_run=True)，不应实际删除文件
    preview = storage.cleanup_materials(dry_run=True)
    assert preview["removed_files_count"] >= 2
    assert junk_file.exists()
    assert orphan_file.exists()

    # 2. 正式清理 (dry_run=False)
    result = storage.cleanup_materials(dry_run=False)
    assert result["removed_files_count"] >= 2
    assert not junk_file.exists()
    assert not orphan_file.exists()
    assert result["freed_bytes"] >= (len(b"dummy_junk_123") + len(b"dummy_orphan_456"))


def test_cleanup_dedup_and_project_retargeting():
    storage = StorageService()
    proj_repo = ProjectRepository()
    content = b"sample_talking_head_speech_video_bytes"

    # 保存原始权威素材
    mat_authoritative = storage.save_material(MaterialCategory.TALKING_HEAD, "speech_v1.mp4", content)

    # 模拟历史冗余脏数据：向 materials 插入一个相同 hash 但不同 ID 的重复记录
    from app.models.entities import Material
    dup_mat = Material(
        id="mat-dup-historical-id",
        category=MaterialCategory.TALKING_HEAD,
        filename="speech_v2_dup.mp4",
        filepath=mat_authoritative.filepath,
        content_hash=mat_authoritative.content_hash,
        file_size=mat_authoritative.file_size
    )
    storage.repo.save(dup_mat)
    assert storage.repo.get_by_id("mat-dup-historical-id") is not None

    # 工程 1 引用权威素材
    proj1 = CutProject(
        id="test-proj-authoritative",
        title="权威工程",
        talking_head_id=mat_authoritative.id
    )
    proj_repo.save(proj1)

    # 工程 2 引用重复素材 dup_mat.id
    proj2 = CutProject(
        id="test-proj-retarget-2",
        title="待重定向工程",
        talking_head_id=dup_mat.id
    )
    proj_repo.save(proj2)

    # 执行清理
    cleanup_res = storage.cleanup_materials(dry_run=False)
    assert cleanup_res["merged_materials_count"] >= 1

    # 验证：dup_mat 记录已被合并删除
    assert storage.repo.get_by_id("mat-dup-historical-id") is None
    # 验证：权威素材仍然保留
    assert storage.repo.get_by_id(mat_authoritative.id) is not None
    # 验证：工程 2 的 talking_head_id 已自动无损重定向到权威记录 mat_authoritative.id
    updated_proj2 = proj_repo.get_by_id("test-proj-retarget-2")
    assert updated_proj2.talking_head_id == mat_authoritative.id


def test_cleanup_api_endpoint():
    res = client.post("/api/v1/materials/cleanup?dry_run=false")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == 0
    assert "freed_mb" in data["data"]
    assert "removed_files_count" in data["data"]
    assert "merged_materials_count" in data["data"]
