"""剪辑工程自愈与级联防误删专项测试：
1. 验证素材删除绝不级联物理删除已完成成片工程
2. 验证同一口播素材保存多个版本/批剪成片时互不覆盖删除
3. 验证从自包含任务目录 project_manifest.json 与 subtitles.srt 自动自愈恢复未入库工程
4. 验证单个工程删除仅针对目标工程，不误删同素材其他工程
"""
import os
import json
import tempfile
from pathlib import Path
import pytest

from app.core.config import TASKS_DIR, STORAGE_DIR
from app.models.entities import MaterialCategory, CutProject, CutProjectStatus
from app.native_engine.storage import StorageService
from app.native_engine.project_storage import project_storage_service
from app.db.repository import MaterialRepository, ProjectRepository

def test_material_deletion_does_not_cascade_delete_completed_projects():
    storage = StorageService()
    mat = storage.save_material(MaterialCategory.TALKING_HEAD, "th_preserve_test.mp4", b"dummy_preserve_video_bytes_123")
    
    proj = CutProject(
        id="proj-preserve-completed-1",
        title="已完成重要成片",
        talking_head_id=mat.id,
        status=CutProjectStatus.COMPLETED,
        output_video_path="storage/tasks/dummy_preserve/final.mp4"
    )
    project_storage_service.save_project(proj)
    assert project_storage_service.get_by_project_id(proj.id) is not None

    # 删除素材（如素材库维护）
    storage.delete_material(mat.id)
    
    # 核心保障：已完成工程依然完好无损
    preserved_p = project_storage_service.get_by_project_id(proj.id)
    assert preserved_p is not None
    assert preserved_p.title == "已完成重要成片"

def test_saving_multiple_projects_for_same_material():
    mat_repo = MaterialRepository()
    mat = storage = StorageService().save_material(MaterialCategory.TALKING_HEAD, "th_multi_proj.mp4", b"dummy_multi_proj_bytes")
    
    # 同一素材产出两个不同成片版本 (例如竖屏与横屏)
    proj1 = CutProject(id="proj-ver-1", title="版本1", talking_head_id=mat.id, status=CutProjectStatus.COMPLETED)
    proj2 = CutProject(id="proj-ver-2", title="版本2", talking_head_id=mat.id, status=CutProjectStatus.COMPLETED)
    
    project_storage_service.save_project(proj1)
    project_storage_service.save_project(proj2)
    
    # 两个工程必须同时存在，互不覆盖抹除
    assert project_storage_service.get_by_project_id("proj-ver-1") is not None
    assert project_storage_service.get_by_project_id("proj-ver-2") is not None

def test_self_healing_from_task_manifest(tmp_path):
    task_dir = TASKS_DIR / "20260999_999999_test_heal_task"
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 构造合法的真实视频文件 (> 10KB)
    vid_file = task_dir / "output_heal_test.mp4"
    vid_file.write_bytes(b"0" * 15000)
    
    # 构造 subtitles.srt
    srt_file = task_dir / "subtitles.srt"
    srt_content = """1
00:00:00,100 --> 00:00:02,500
自愈测试第一句字幕

2
00:00:02,500 --> 00:00:05,000
自愈测试第二句字幕
"""
    srt_file.write_text(srt_content, encoding="utf-8")
    
    manifest_file = task_dir / "project_manifest.json"
    manifest_data = {
        "project_id": "proj-heal-target-99",
        "title": "自动自愈成片",
        "aspect_ratio": "9:16",
        "status": "completed",
        "talking_head_id": "th-dummy-heal-id",
        "task_dir": str(task_dir.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
        "output_video_path": str(vid_file.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
        "cover_image_path": None,
        "cover_source": "frame"
    }
    manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False), encoding="utf-8")
    
    try:
        # 执行自愈
        project_storage_service._heal_from_disk()
        
        healed = project_storage_service.get_by_project_id("proj-heal-target-99")
        assert healed is not None
        assert healed.title == "自动自愈成片"
        assert healed.status == CutProjectStatus.COMPLETED
        assert len(healed.subtitles) == 2
        assert healed.subtitles[0].raw_text == "自愈测试第一句字幕"
        assert healed.subtitles[1].raw_text == "自愈测试第二句字幕"
    finally:
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)

def test_delete_project_only_deletes_specified():
    proj1 = CutProject(id="proj-del-a", title="待删工程", talking_head_id="th-del-shared", status=CutProjectStatus.COMPLETED)
    proj2 = CutProject(id="proj-keep-b", title="保留工程", talking_head_id="th-del-shared", status=CutProjectStatus.COMPLETED)
    
    project_storage_service.save_project(proj1)
    project_storage_service.save_project(proj2)
    
    assert project_storage_service.delete_project("proj-del-a") is True
    assert project_storage_service.get_by_project_id("proj-del-a") is None
    assert project_storage_service.get_by_project_id("proj-keep-b") is not None

def test_shadow_json_removed_on_delete_prevents_resurrection():
    proj = CutProject(id="proj-shadow-test", title="影子工程", talking_head_id="th-shadow-test", status=CutProjectStatus.DRAFT)
    project_storage_service.save_project(proj)
    
    # 模拟在 storage/projects 生成影子 JSON
    shadow_file = project_storage_service.storage_dir / f"{proj.id}.json"
    shadow_file.parent.mkdir(parents=True, exist_ok=True)
    shadow_file.write_text(json.dumps(proj.dict(), ensure_ascii=False), encoding="utf-8")
    assert shadow_file.exists()
    
    # 执行删除工程
    assert project_storage_service.delete_project(proj.id) is True
    # 影子文件必须被彻底移除
    assert not shadow_file.exists()
    
    # 再次触发自愈，确保不会复活
    project_storage_service._heal_from_disk()
    assert project_storage_service.get_by_project_id(proj.id) is None

def test_broken_draft_auto_pruning():
    # 构造一个引用了不存在素材的死草稿
    ghost_proj = CutProject(
        id="proj-ghost-draft",
        title="幽灵草稿",
        talking_head_id="non-existent-material-id-999",
        status=CutProjectStatus.DRAFT,
        output_video_path=None
    )
    project_storage_service.save_project(ghost_proj)
    assert project_storage_service.get_by_project_id("proj-ghost-draft") is not None
    
    # 执行失效草稿巡检清理
    cleaned = project_storage_service.prune_broken_drafts()
    assert cleaned >= 1
    assert project_storage_service.get_by_project_id("proj-ghost-draft") is None
