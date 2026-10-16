import pytest
import time
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.models.entities import (
    CutProject,
    CutProjectStatus,
    MaterialCategory,
    EditingStrategy,
    SubtitleSegment,
    CoverDesignConfig,
)
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.native_engine.ffmpeg_filter import composer

client = TestClient(app)

def test_fast_path_cover_caching_and_splicing(tmp_path, monkeypatch):
    """
    验证封面插入极速通道（Fast-Path）：
    1. 首次渲染生成 _base_composition.mp4 底包。
    2. 仅更新封面并再次渲染时，命中底包指纹缓存，完全跳过 compose_jl_cut 全片重编码，
       仅通过 concat -c copy 毫秒级拼接完成（耗时 < 1s）。
    3. 字幕内容变动时，指纹失效，重新触发 compose_jl_cut。
    """
    # 1. 注册测试素材与工程
    th_file = tmp_path / "th_fastpath.mp4"
    th_file.write_bytes(b"stream_th_fastpath_bytes")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_fastpath.mp4", th_file)

    proj = CutProject(
        id="proj_fastpath_test",
        title="极速封面合成测试",
        talking_head_id=th.id,
        status=CutProjectStatus.DRAFT,
        subtitles=[
            SubtitleSegment(start_time=0.0, end_time=3.0, raw_text="学车找我们不用踩坑", corrected_text="学车找我们不用踩坑"),
            SubtitleSegment(start_time=3.0, end_time=6.0, raw_text="价格全包没有隐形收费", corrected_text="价格全包没有隐形收费"),
        ],
        strategy=EditingStrategy(embed_cover_as_first_frame=True)
    )
    project_storage_service.save_project(proj)

    compose_call_count = 0
    original_compose = composer.compose_jl_cut

    def mock_compose(*args, **kwargs):
        nonlocal compose_call_count
        compose_call_count += 1
        out_p = kwargs["output_path"]
        out_p.parent.mkdir(parents=True, exist_ok=True)
        # 写入虚拟有效 MP4 字节流
        out_p.write_bytes(b"fake_mp4_body_bytes_valid_stream")
        return True

    monkeypatch.setattr(composer, "compose_jl_cut", mock_compose)

    try:
        # --- 轮次 1: 首次渲染 ---
        t0 = time.time()
        res1 = client.post(f"/api/v1/projects/{proj.id}/render?include_cover=false")
        assert res1.status_code == 200
        assert compose_call_count == 1, "首次渲染必须调用 compose_jl_cut"

        loaded_p1 = project_storage_service.get_by_project_id(proj.id)
        from app.core.config import STORAGE_DIR
        task_dir = (STORAGE_DIR.parent / loaded_p1.task_dir).resolve()
        base_comp = task_dir / "_base_composition.mp4"
        base_meta = task_dir / "_base_composition.meta.json"
        assert base_comp.exists(), "_base_composition.mp4 底包必须生成"
        assert base_meta.exists(), "_base_composition.meta.json 元数据必须落盘"

        # --- 轮次 2: 仅配置封面，再次触发渲染 ---
        proj_updated = project_storage_service.get_by_project_id(proj.id)
        proj_updated.cover_config = CoverDesignConfig(
            template_id="sticker_double_stroke",
            main_title="加封面极速测试",
            sub_title="毫秒级生成",
            color_theme="classic_blue"
        )
        project_storage_service.save_project(proj_updated)

        t1 = time.time()
        res2 = client.post(f"/api/v1/projects/{proj.id}/render?include_cover=true&embed_cover_as_first_frame=false")
        cost_seconds = time.time() - t1
        assert res2.status_code == 200
        # 核心断言：未改变视频主体，命中底包缓存，compose_jl_cut 调用次数必须依然为 1！
        assert compose_call_count == 1, f"仅加封面时必须复用底包缓存，严禁重新全片编码！调用次数: {compose_call_count}"
        assert cost_seconds < 2.0, f"仅加封面必须毫秒级响应，实际耗时: {cost_seconds:.2f}s"

        # --- 轮次 3: 修改视频主体属性（画幅/倍速），再次触发渲染 ---
        proj_updated2 = project_storage_service.get_by_project_id(proj.id)
        proj_updated2.aspect_ratio = "16:9"
        project_storage_service.save_project(proj_updated2)

        res3 = client.post(f"/api/v1/projects/{proj.id}/render?include_cover=true&embed_cover_as_first_frame=false")
        assert res3.status_code == 200
        # 核心断言：视频主体改动后，指纹不一致，必须重新调用 compose_jl_cut 生成最新成片
        assert compose_call_count == 2, f"主体变动后必须重新调用 compose_jl_cut！实际次数: {compose_call_count}"

    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)


def test_single_pass_direct_render_without_double_encode(tmp_path, monkeypatch):
    """
    验证底包未命中时的单次直出优化：
    底包未命中时，系统直接调用一次 compose_jl_cut 一体化完成切片、空镜、调色与 ASS 字幕压制，
    绝不先调用 compose_clean_base 再调用 burn_subtitles_and_overlay_fast 造成两次全量重编码。
    """
    th_file = tmp_path / "th_singlepass.mp4"
    th_file.write_bytes(b"stream_th_singlepass_bytes")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_singlepass.mp4", th_file)

    proj = CutProject(
        id="proj_singlepass_test",
        title="单次直出渲染测试",
        talking_head_id=th.id,
        status=CutProjectStatus.DRAFT,
        subtitles=[
            SubtitleSegment(start_time=0.0, end_time=2.0, raw_text="测试单次极速合成", corrected_text="测试单次极速合成"),
        ],
        strategy=EditingStrategy(embed_cover_as_first_frame=False)
    )
    project_storage_service.save_project(proj)

    calls = {"jl_cut": 0, "fast_burn": 0}

    def mock_compose(*args, **kwargs):
        calls["jl_cut"] += 1
        # 断言直接传入了 ass 字幕路径，证实是一次性单次全流程压制！
        assert kwargs.get("ass_subtitle_path") is not None, "单次直出必须直接带入 ass_subtitle_path！"
        out_p = kwargs["output_path"]
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"fake_single_pass_mp4_bytes")
        return True

    def mock_burn(*args, **kwargs):
        calls["fast_burn"] += 1
        return True

    monkeypatch.setattr(composer, "compose_jl_cut", mock_compose)
    monkeypatch.setattr(composer, "burn_subtitles_and_overlay_fast", mock_burn)

    try:
        res = client.post(f"/api/v1/projects/{proj.id}/render?include_cover=false")
        assert res.status_code == 200
        # 核心断言：必须仅调用 1 次 compose_jl_cut 直出，绝不额外调用 fast_burn 进行二次重编码！
        assert calls["jl_cut"] == 1, f"单次直出必须刚好调用 1 次 compose_jl_cut，实际: {calls['jl_cut']}"
        assert calls["fast_burn"] == 0, f"底包失效时不应触发二次 fast_burn，实际调用了: {calls['fast_burn']}"
    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)

