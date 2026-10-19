import pytest
from pathlib import Path
from app.core.config import STORAGE_DIR, resolve_media_path, to_storage_relative
from app.native_engine.ffmpeg_filter import composer

def test_build_ass_filter_expr_with_chinese_and_windows_path(tmp_path):
    """验证包含中文字符与 Windows 冒号的字幕目录，能正确输出纯 ASCII 相对路径 ass=subtitles.ass"""
    # 模拟包含中文与空格的 Windows 任务输出目录（正是用户报错的环境）
    chinese_task_dir = tmp_path / "20261019_160721_微信视频2026-10-19_160404_438"
    chinese_task_dir.mkdir(parents=True, exist_ok=True)
    ass_file = chinese_task_dir / "subtitles.ass"
    ass_file.write_text("[Script Info]\nTitle: Test\n", encoding="utf-8")

    # 当 work_dir 提供时，必须输出 ass=subtitles.ass，杜绝盘符冒号与编码导致的 libass fopen failed
    expr = composer._build_ass_filter_expr(ass_file, work_dir=chinese_task_dir)
    assert expr == "ass=subtitles.ass"

def test_resolve_media_path_relative_and_legacy(tmp_path):
    """验证全生命周期路径自愈解析器 resolve_media_path"""
    # 1. 真实存在于当前 STORAGE_DIR 的相对路径
    sample_file = STORAGE_DIR / "materials" / "talking_head" / "unit_test_video.mp4"
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    sample_file.write_bytes(b"fake video data")

    # 测试带 storage 前缀相对路径
    p1 = resolve_media_path("storage/materials/talking_head/unit_test_video.mp4")
    assert p1 is not None and p1.exists()
    assert p1.resolve() == sample_file.resolve()

    # 测试无 storage 前缀相对路径
    p2 = resolve_media_path("materials/talking_head/unit_test_video.mp4")
    assert p2 is not None and p2.exists()
    assert p2.resolve() == sample_file.resolve()

    # 2. 模拟来自另一台电脑或更新前旧目录的绝对路径（旧盘符或旧文件夹）
    legacy_abs_path = "D:/old_version_videocut/storage/materials/talking_head/unit_test_video.mp4"
    p3 = resolve_media_path(legacy_abs_path)
    assert p3 is not None and p3.exists()
    assert p3.resolve() == sample_file.resolve()

    # 3. 待生成的成片目标路径（物理文件尚未落地）
    target_rel = "storage/tasks/20261019_999999_test/rendered_out.mp4"
    p4 = resolve_media_path(target_rel)
    assert p4 is not None
    assert "storage" in str(p4) and str(p4).endswith("rendered_out.mp4")

def test_to_storage_relative_normalization():
    """验证 to_storage_relative 统一规范化为数据库持久相对路径"""
    expected_prefix = f"{STORAGE_DIR.name}/"
    assert to_storage_relative(f"D:/Program Files/VideoCut/storage/tasks/clip/subtitles.ass") == f"{expected_prefix}tasks/clip/subtitles.ass"
    assert to_storage_relative(r"C:\Users\User\AppData\Local\videocut\storage\materials\th.mp4") == f"{expected_prefix}materials/th.mp4"
    assert to_storage_relative("storage/outputs/clip.mp4") == f"{expected_prefix}outputs/clip.mp4"
    assert to_storage_relative("") == ""
