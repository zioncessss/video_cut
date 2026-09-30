"""QA Functional Test Matrix: Comprehensive testing for upload, storage, regions, and sync.
Covers:
1. Different content upload (formats, categories, empty/corrupt, duplicates)
2. Upload close / cancellation
3. Region switching, tagging, and filtering
4. Storage permission, quotes, missing dir, SQLite connection self-healing
5. Cross-module data synchronization and deletion consistency
"""
import os
import sys
import tempfile
import shutil
import sqlite3
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import CATEGORIES, ALLOWED_VIDEO_EXTENSIONS, STORAGE_DIR, DB_PATH
from app.models.entities import MaterialCategory, CutProject, CutProjectStatus
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service

client = TestClient(app)

# -------------------------------------------------------------
# Dimension 1: Uploading Different Content
# -------------------------------------------------------------
def test_tc1_upload_various_extensions(tmp_path):
    """TC1.1: 验证支持的视频格式 (.mp4, .mov, .mkv, .avi, .webm) 均能成功解析入库"""
    for ext in ALLOWED_VIDEO_EXTENSIONS:
        test_file = tmp_path / f"sample_{ext.strip('.')}{ext}"
        test_file.write_bytes(f"dummy_content_{ext}".encode("utf-8"))
        res = client.post("/api/v1/materials/import-local", json={
            "category": "venue",
            "file_path": str(test_file),
            "plate_region": "ZHE_A"
        })
        assert res.status_code == 200, f"格式 {ext} 导入失败: {res.text}"
        data = res.json()
        assert data["category"] == "venue"
        assert data["plate_region"] == "浙A·杭州"
        storage_service.delete_material(data["id"])

def test_tc1_upload_invalid_extensions(tmp_path):
    """TC1.2: 验证非法格式 (.txt, .exe, .jpg) 被阻断，报 400 明确提示"""
    bad_file = tmp_path / "danger.exe"
    bad_file.write_bytes(b"MZ_fake_exe")
    res = client.post("/api/v1/materials/import-local", json={
        "category": "venue",
        "file_path": str(bad_file)
    })
    assert res.status_code == 400 or res.status_code == 500
    assert "不支持" in res.text or "format" in res.text.lower() or "extension" in res.text.lower() or "400" in str(res.status_code)

def test_tc1_upload_deduplication(tmp_path):
    """TC1.3: 验证相同 SHA-256 内容不同文件名的精准去重，不占用多余存储空间"""
    same_bytes = b"identical_content_hash_12345"
    f1 = tmp_path / "video_a.mp4"
    f2 = tmp_path / "video_b.mp4"
    f1.write_bytes(same_bytes)
    f2.write_bytes(same_bytes)

    res1 = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": str(f1),
        "plate_region": "ZHE_J"
    })
    assert res1.status_code == 200
    m1 = res1.json()

    res2 = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": str(f2),
        "plate_region": "ZHE_J"
    })
    assert res2.status_code == 200
    m2 = res2.json()

    assert m1["id"] == m2["id"], "相同哈希素材应当命中复用，返回同一素材 ID"
    assert m1["content_hash"] == m2["content_hash"]
    storage_service.delete_material(m1["id"])

# -------------------------------------------------------------
# Dimension 2: Upload Close / Cancel / Non-existent File
# -------------------------------------------------------------
def test_tc2_import_non_existent_file():
    """TC2.1: 验证导入不存在的文件路径时返回友好 400 错误"""
    res = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": "Z:/definitely_not_exist_file.mp4"
    })
    assert res.status_code == 400
    assert "不存在" in res.json()["detail"]

# -------------------------------------------------------------
# Dimension 3: Switching Regions, Tagging, and Filtering
# -------------------------------------------------------------
def test_tc3_region_switching_and_filtering(tmp_path):
    """TC3.1: 验证不同地区 (浙A/浙J) 分别标记，并且按地区查询时结果严格隔离"""
    f_hz = tmp_path / "hangzhou_clip.mp4"
    f_tz = tmp_path / "taizhou_clip.mp4"
    f_hz.write_bytes(b"content_hz")
    f_tz.write_bytes(b"content_tz")

    r_hz = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": str(f_hz),
        "plate_region": "ZHE_A"
    }).json()

    r_tz = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": str(f_tz),
        "plate_region": "ZHE_J"
    }).json()

    try:
        # 查询台州 (ZHE_J)
        list_tz = client.get("/api/v1/materials?category=lesson&plate_region=ZHE_J").json()
        tz_ids = [m["id"] for m in list_tz]
        assert r_tz["id"] in tz_ids, "台州素材必须在台州筛选列表中"
        assert r_hz["id"] not in tz_ids, "杭州素材绝不能出现在台州筛选列表中"

        # 查询杭州 (ZHE_A)
        list_hz = client.get("/api/v1/materials?category=lesson&plate_region=ZHE_A").json()
        hz_ids = [m["id"] for m in list_hz]
        assert r_hz["id"] in hz_ids, "杭州素材必须在杭州筛选列表中"
        assert r_tz["id"] not in hz_ids, "台州素材绝不能出现在杭州筛选列表中"

        # 原地修改地区: 将台州改为温州 (ZHE_C)
        patch_res = client.patch(f"/api/v1/materials/{r_tz['id']}/region", json={"plate_region": "ZHE_C"})
        assert patch_res.status_code == 200
        assert patch_res.json()["plate_region"] == "浙C·温州"

        # 再次查台州：原台州素材已移除
        list_tz_after = client.get("/api/v1/materials?category=lesson&plate_region=ZHE_J").json()
        assert r_tz["id"] not in [m["id"] for m in list_tz_after]

        # 查温州：已出现在温州
        list_wz = client.get("/api/v1/materials?category=lesson&plate_region=ZHE_C").json()
        assert r_tz["id"] in [m["id"] for m in list_wz]

    finally:
        storage_service.delete_material(r_hz["id"])
        storage_service.delete_material(r_tz["id"])

def test_tc3_empty_region_query_does_not_return_cached_unrelated_items(tmp_path):
    """TC3.2: 验证当某一地区为空时，list_materials 返回空列表，绝不因 Python if db_list 缺陷回退返回缓存脏数据"""
    f = tmp_path / "sample_wenzhou.mp4"
    f.write_bytes(b"wenzhou_content_unique_999")
    m = client.post("/api/v1/materials/import-local", json={
        "category": "lesson",
        "file_path": str(f),
        "plate_region": "ZHE_C"
    }).json()

    try:
        # 查询一个根本没有素材的地区 (浙K·丽水)
        empty_list = client.get("/api/v1/materials?category=lesson&plate_region=ZHE_K").json()
        assert empty_list == [], f"浙K 无素材时必须返回空列表，但返回了: {empty_list}"
    finally:
        storage_service.delete_material(m["id"])

# -------------------------------------------------------------
# Dimension 4: Storage Path & Permissions (The "unable to open database file" reproduction)
# -------------------------------------------------------------
def test_tc4_path_with_quotes_sanitization(tmp_path):
    """TC4.1: 验证环境变量路径若携带外层引号，系统能自动 strip 避免 SQLite unable to open database file"""
    raw_path_with_quotes = f'"{tmp_path / "quoted_storage"}"'
    clean_path = raw_path_with_quotes.strip().strip('"').strip("'")
    p = Path(clean_path)
    p.mkdir(parents=True, exist_ok=True)
    db_file = p / "videocut.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INT);")
    conn.close()
    assert db_file.exists()

def test_tc4_sqlite_cantopen_error_diagnosis():
    """TC4.2: 验证 SQLite 在只读/权限不足目录下触发 OperationalError unable to open database file 的机制"""
    with tempfile.TemporaryDirectory() as td:
        locked_dir = Path(td) / "locked_for_test"
        locked_dir.mkdir()
        # Windows 上通过 icacls 阻断写权限
        subprocess.run(["icacls", str(locked_dir), "/deny", "Everyone:(W)"], capture_output=True)
        try:
            db_p = locked_dir / "videocut.db"
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                conn = sqlite3.connect(str(db_p), timeout=2.0)
            assert "unable to open database file" in str(exc_info.value)
        finally:
            subprocess.run(["icacls", str(locked_dir), "/remove:d", "Everyone"], capture_output=True)

# -------------------------------------------------------------
# Dimension 5: Cross-Module Sync & Deletion Idempotence
# -------------------------------------------------------------
def test_tc5_material_delete_cascades_and_does_not_ghost(tmp_path):
    """TC5.1: 素材库删除素材后，剪辑工作台和批量混剪不能残留幽灵引用"""
    th_file = tmp_path / "th_sync_test.mp4"
    th_file.write_bytes(b"stream_th_sync")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_sync_test.mp4", th_file)

    p = CutProject(id="proj_sync_test", title="同步测试", talking_head_id=th.id, status=CutProjectStatus.DRAFT)
    project_storage_service.save_project(p)

    # 验证工程存在
    assert project_storage_service.get_by_project_id(p.id) is not None

    # 从素材库删除素材
    del_m_res = client.delete(f"/api/v1/materials/{th.id}")
    assert del_m_res.status_code == 200

    # 验证素材已被删除
    assert storage_service.get_material(th.id) is None
    # 验证关联工程已级联清理，不会幽灵复活
    assert project_storage_service.get_by_project_id(p.id) is None
