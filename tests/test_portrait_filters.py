import pytest
import shutil
from pathlib import Path
from app.native_engine.ffmpeg_filter import (
    composer,
    PORTRAIT_PRESETS,
    build_portrait_filter_chain,
    _extract_ffmpeg_error
)
from app.models.entities import EditingStrategy

def test_filter_presets_registry():
    """验证口播滤镜预设完整性与参数合理性"""
    assert "clean_natural" in PORTRAIT_PRESETS
    assert "crisp_hd" in PORTRAIT_PRESETS
    assert "warm_radiant" in PORTRAIT_PRESETS
    assert "original" in PORTRAIT_PRESETS

    natural = PORTRAIT_PRESETS["clean_natural"]
    assert natural is not None
    assert 1.01 <= natural.eq_contrast <= 1.15
    assert 0.0 <= natural.eq_brightness <= 0.08
    assert 1.01 <= natural.eq_saturation <= 1.20
    assert 1.01 <= natural.eq_gamma <= 1.10
    assert 0.15 <= natural.cas_strength <= 0.50
    assert natural.smartblur_lt < 0  # 负阈值保护边缘，仅平滑平坦区

    assert PORTRAIT_PRESETS["original"] is None  # original 必须为 None (Bypass)

def test_build_portrait_filter_chain_full_strength():
    """验证全强度下滤镜字符串组装"""
    chain = build_portrait_filter_chain("clean_natural", strength=1.0)
    assert "smartblur=" in chain
    assert "eq=" in chain
    assert "contrast=1.040" in chain
    assert "brightness=0.020" in chain
    assert "saturation=1.060" in chain
    assert "gamma=1.030" in chain
    assert "cas=0.30" in chain or "unsharp=" in chain

def test_build_portrait_filter_chain_original_and_zero_strength():
    """验证 original 预设与 0 强度完全旁路 (Bypass)，零冗余指令"""
    assert build_portrait_filter_chain("original", strength=1.0) == ""
    assert build_portrait_filter_chain("clean_natural", strength=0.0) == ""
    assert build_portrait_filter_chain("crisp_hd", strength=0.005) == ""

def test_build_portrait_filter_chain_interpolation():
    """验证强度线性衰减插值 (50% 强度)"""
    chain_50 = build_portrait_filter_chain("clean_natural", strength=0.5)
    # contrast 1.040 -> 1.0 + (1.04 - 1.0)*0.5 = 1.020
    assert "contrast=1.020" in chain_50
    # brightness 0.020 -> 0.0 + 0.02*0.5 = 0.010
    assert "brightness=0.010" in chain_50
    # saturation 1.060 -> 1.0 + 0.06*0.5 = 1.030
    assert "saturation=1.030" in chain_50
    # cas 0.30 -> 0.15
    assert "cas=0.15" in chain_50 or "luma_amount=0.15" in chain_50

def test_black_border_defense_in_normalize_filter():
    """
    黑边防变灰铁律测试：
    口播调色与锐化必须作用于画面内容 (scale 之后)，
    且必须在补齐黑边 (pad) 之前完成，绝不能让 eq 滤镜将纯黑边亮化变灰！
    """
    filter_str = composer.build_color_normalize_filter(
        is_hdr=False,
        target_w=1080,
        target_h=1920,
        filter_preset="clean_natural",
        filter_strength=1.0
    )
    scale_idx = filter_str.find("scale=1080:1920")
    portrait_idx = filter_str.find("eq=")
    pad_idx = filter_str.find("pad=1080:1920")

    assert scale_idx != -1
    assert portrait_idx != -1
    assert pad_idx != -1
    # 验证严格顺序：scale -> portrait_filter -> pad
    assert scale_idx < portrait_idx < pad_idx

def test_color_normalize_filter_ffmpeg_cross_version_compatibility():
    """
    跨版本 FFmpeg 滤镜语法兼容性测试：
    1. 确保绝对不包含低版本 FFmpeg (如 6.x) 不支持的 AMBIENT_VIEWING_ENVIRONMENT 等不稳定参数。
    2. 确保色彩归一化必须严格输出标准的 yuv420p 与 bt709 标头。
    3. 若本地或打包目录存在真实的 FFmpeg 6.x 二进制，通过真实滤镜图校验 100% 语法合法。
    """
    import subprocess
    from app.core.config import get_ffmpeg_cmd

    filter_sdr = composer.build_color_normalize_filter(is_hdr=False, target_w=1080, target_h=1920)
    filter_hdr = composer.build_color_normalize_filter(is_hdr=True, target_w=1080, target_h=1920)

    # 1. 严格断言不包含破坏性参数
    assert "AMBIENT_VIEWING_ENVIRONMENT" not in filter_sdr
    assert "AMBIENT_VIEWING_ENVIRONMENT" not in filter_hdr

    # 2. 严格断言包含工业级标准色彩标头
    assert "format=yuv420p" in filter_sdr
    assert "color_primaries=bt709:color_trc=bt709:colorspace=bt709" in filter_sdr

    # 3. 针对现存的 FFmpeg 二进制（包含 6.1.1 与 8.x）进行真实 filtergraph 解析验证
    ffmpeg_candidates = [
        get_ffmpeg_cmd(),
        "D:/Program Files (x86)/VideoCut/resources/engine/bin/ffmpeg.exe"
    ]
    for ff in ffmpeg_candidates:
        if ff and Path(ff).exists():
            test_cmd = [
                str(ff), "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=0.04",
                "-vf", filter_sdr,
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert res.returncode == 0, f"FFmpeg ({ff}) 解析 SDR 归一化滤镜失败: {res.stderr.decode('utf-8', errors='replace')}"

def test_extract_ffmpeg_error_diagnostic_quality():
    """验证 _extract_ffmpeg_error 能够准确提取 FFmpeg stderr 中的根因行，而不是机械截断"""
    sample_stderr = """
ffmpeg version 6.1.1-essentials_build-www.gyan.dev
Input #0, lavfi, from 'color=c=blue:s=1280x720:d=1':
[Parsed_sidedata_0 @ 00000223aa25f7c0] [Eval @ 00000086a1bfdcf0] Undefined constant or missing '(' in 'AMBIENT_VIEWING_ENVIRONMENT'
[Parsed_sidedata_0 @ 00000223aa25f7c0] Unable to parse option value "AMBIENT_VIEWING_ENVIRONMENT"
Error applying option 'type' to filter 'sidedata': Invalid argument
[vost#0:0/wrapped_avframe @ 00000223aa25e940] Error initializing a simple filtergraph
Error opening output file -.
Error opening output files: Invalid argument
    """
    extracted = _extract_ffmpeg_error(sample_stderr)
    assert "Undefined constant or missing" in extracted
    assert "Unable to parse option value" in extracted
    assert "Error applying option 'type'" in extracted


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="需要本地 FFmpeg 支持")
def test_real_video_render_with_portrait_filter(tmp_path):
    """端到端合成测试：应用口播滤镜真实压制一段真实小样视频"""
    sample_videos = list(Path("storage/materials/talking_head").glob("*.mp4"))
    real_sample = None
    for v in sample_videos:
        if v.stat().st_size > 10240:
            real_sample = v
            break

    if not real_sample:
        pytest.skip("未发现大于10KB的真实口播测试素材，跳过真机压制测试")

    out_file = tmp_path / "output_filter_test.mp4"
    strat = EditingStrategy(
        filter_preset="clean_natural",
        filter_strength=1.0,
        show_subtitles=False
    )

    from app.models.entities import KeptSpan
    kept = [KeptSpan(start_time=0.0, end_time=1.0, duration=1.0, audio_fade=True)]

    success = composer.compose_jl_cut(
        talking_head_path=real_sample,
        broll_cuts=[],
        output_path=out_file,
        aspect_ratio="9:16",
        total_duration=1.0,
        strategy=strat.model_dump(),
        kept_spans=kept
    )

    assert success is True
    assert out_file.exists()
    assert out_file.stat().st_size > 10240

def test_get_filter_presets_api():
    """验证 GET /api/v1/editor/filter-presets API 接口返回格式与数据完整性"""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/editor/filter-presets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    presets = data["data"]
    preset_ids = [p["id"] for p in presets]
    assert "clean_natural" in preset_ids
    assert "crisp_hd" in preset_ids
    assert "warm_radiant" in preset_ids
    assert "original" in preset_ids

    # 验证推荐标识
    rec_preset = next((p for p in presets if p.get("is_recommended")), None)
    assert rec_preset is not None
    assert rec_preset["id"] in ("cold_white", "clean_natural")
    assert len(rec_preset["tags"]) > 0
