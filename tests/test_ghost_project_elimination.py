"""
幽灵工程消除与数据生命周期安全测试 (013-system-resilience-ux: US1)
测试目标：
1. 删除工程或口播素材时，物理任务目录 (storage/tasks/<task_dir>) 100% 干净删除，重启后绝不幽灵复活。
2. _heal_from_disk 扫描磁盘时，若 talking_head_id 在 materials 表中不存在，就地销毁残余目录，禁止恢复入库。
3. 删除空镜素材时，存量工程引用的 broll_material_id 与 broll_replacements 被安全解绑置空，防止压制崩溃。
"""
import json
import shutil
from pathlib import Path
import pytest

from app.core.config import TASKS_DIR, STORAGE_DIR
from app.models.entities import (
    Material,
    MaterialCategory,
    CutProject,
    CutProjectStatus,
    SubtitleSegment,
    BrollReplacement,
    EditingStrategy,
)
from app.native_engine.storage import StorageService
from app.native_engine.project_storage import project_storage_service
from app.db.repository import MaterialRepository, ProjectRepository


def test_delete_project_cleans_up_task_dir_and_prevents_ghost_resurrection(tmp_path):
    storage = StorageService()
    mat = storage.save_material(MaterialCategory.TALKING_HEAD, "th_ghost_test.mp4", b"dummy_th_ghost_bytes")
    
    # 构造专属任务目录
    task_dir_name = "20260999_test_ghost_clean"
    task_dir = TASKS_DIR / task_dir_name
    task_dir.mkdir(parents=True, exist_ok=True)
    
    vid_file = task_dir / "output_ghost_test.mp4"
    vid_file.write_bytes(b"0" * 15000)
    
    srt_file = task_dir / "subtitles.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:02,000\n幽灵测试字幕\n", encoding="utf-8")
    
    manifest_file = task_dir / "project_manifest.json"
    proj_id = "proj-ghost-clean-01"
    manifest_data = {
        "project_id": proj_id,
        "title": "幽灵清理测试工程",
        "aspect_ratio": "9:16",
        "status": "completed",
        "talking_head_id": mat.id,
        "task_dir": str(task_dir.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
        "output_video_path": str(vid_file.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
    }
    manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")

    proj = CutProject(
        id=proj_id,
        title="幽灵清理测试工程",
        talking_head_id=mat.id,
        status=CutProjectStatus.COMPLETED,
        task_dir=str(task_dir.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
        output_video_path=str(vid_file.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
    )
    project_storage_service.save_project(proj)
    assert project_storage_service.get_by_project_id(proj_id) is not None
    assert task_dir.exists() is True

    # 执行删除工程
    deleted = project_storage_service.delete_project(proj_id, delete_files=True)
    assert deleted is True
    assert project_storage_service.get_by_project_id(proj_id) is None
    # 物理任务目录必须被彻底清理
    assert task_dir.exists() is False

    # 模拟系统重启触发从磁盘自愈
    project_storage_service._heal_from_disk()
    # 严禁幽灵复活
    assert project_storage_service.get_by_project_id(proj_id) is None


def test_heal_from_disk_destroys_orphan_task_dir_without_material():
    # 模拟磁盘遗留了孤儿任务目录（其口播素材根本不存在于 materials 表）
    task_dir_name = "20260999_orphan_ghost_dir"
    task_dir = TASKS_DIR / task_dir_name
    task_dir.mkdir(parents=True, exist_ok=True)
    
    vid_file = task_dir / "output_orphan.mp4"
    vid_file.write_bytes(b"0" * 15000)
    
    manifest_file = task_dir / "project_manifest.json"
    orphan_proj_id = "proj-orphan-ghost-999"
    manifest_data = {
        "project_id": orphan_proj_id,
        "title": "孤儿残留工程",
        "aspect_ratio": "9:16",
        "status": "completed",
        "talking_head_id": "th-non-existent-id-404",
        "task_dir": str(task_dir.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
        "output_video_path": str(vid_file.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
    }
    manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")

    # 触发自愈
    project_storage_service._heal_from_disk()

    # 孤儿工程不能入库
    assert project_storage_service.get_by_project_id(orphan_proj_id) is None
    # 孤儿目录应被安全就地清理销毁
    assert task_dir.exists() is False


def test_broll_material_deletion_unlinks_project_references_safely():
    storage = StorageService()
    th_mat = storage.save_material(MaterialCategory.TALKING_HEAD, "th_broll_test.mp4", b"dummy_th_bytes")
    broll_mat = storage.save_material(MaterialCategory.VENUE, "venue_broll_test.mp4", b"dummy_venue_bytes")
    
    proj_id = "proj-broll-unbind-test"
    sub = SubtitleSegment(
        id="sub-1",
        start_time=0.0,
        end_time=3.0,
        raw_text="这里是驾校练车场地",
        corrected_text="这里是驾校练车场地",
        broll_material_id=broll_mat.id
    )
    broll_rep = BrollReplacement(
        id="rep-1",
        start_time=0.0,
        end_time=3.0,
        material_id=broll_mat.id,
        material_category=MaterialCategory.VENUE
    )
    proj = CutProject(
        id=proj_id,
        title="空镜解绑测试工程",
        talking_head_id=th_mat.id,
        status=CutProjectStatus.DRAFT,
        subtitles=[sub],
        compact_subtitles=[sub],
        broll_replacements=[broll_rep]
    )
    project_storage_service.save_project(proj)
    
    # 验证保存成功且引用了 broll_mat.id
    saved_p = project_storage_service.get_by_project_id(proj_id)
    assert saved_p is not None
    assert saved_p.subtitles[0].broll_material_id == broll_mat.id
    assert saved_p.compact_subtitles[0].broll_material_id == broll_mat.id
    assert len(saved_p.broll_replacements) == 1

    # 删除空镜素材
    storage.delete_material(broll_mat.id)

    # 重新加载工程，验证空镜已被安全解绑，工程完好无损
    updated_p = project_storage_service.get_by_project_id(proj_id)
    assert updated_p is not None
    assert updated_p.subtitles[0].broll_material_id is None
    if updated_p.compact_subtitles:
        assert updated_p.compact_subtitles[0].broll_material_id is None
    assert len(updated_p.broll_replacements) == 0
