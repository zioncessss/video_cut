"""012 封面渲染引擎纯函数单测：6 大模板 × 4 调色盘、双层描边、拱形弧排、羽化雾化与比例适配。"""
import pytest
from PIL import Image, ImageDraw

from app.core.cover_generator import (
    COVER_PALETTES,
    COVER_TEMPLATES_CATALOG,
    LEGACY_TEMPLATE_IDS,
    _arc_char_positions,
    _build_fog_mask,
    _apply_fog_vignette,
    _draw_double_stroke_text,
    _fit_font_size,
    adapt_image_aspect_ratio,
    get_font,
    render_cover_image,
)
from app.models.entities import CoverDesignConfig

SIX_TEMPLATES = [t["id"] for t in COVER_TEMPLATES_CATALOG]


def _config(**kw) -> CoverDesignConfig:
    defaults = dict(
        template_id="sticker_double_stroke",
        location_tag="武义学车",
        main_title="场地全包含一口价",
        sub_title="先看这个",
        color_theme="classic_blue",
        font_family="heavy_gothic",
    )
    defaults.update(kw)
    return CoverDesignConfig(**defaults)


def _base(w: int = 1080, h: int = 1920, color=(50, 60, 70)) -> Image.Image:
    return Image.new("RGB", (w, h), color=color)


# ---------------------------------------------------------------------------
# 模板目录契约
# ---------------------------------------------------------------------------
def test_templates_catalog_has_all_practical_templates():
    assert SIX_TEMPLATES == [
        "sticker_double_stroke",
        "split_contrast_bar",
        "rainbow_arc_header",
        "bottom_fog_vignette",
        "angled_impact_stamp",
        "clean_editorial",
        "text_behind_person",
        "neon_3d_sticker",
    ]
    for t in COVER_TEMPLATES_CATALOG:
        assert t["name"] and t["category"] and t["badge"] and t["sample_preview"]
        assert t["supported_themes"], f"{t['id']} 缺少推荐调色盘"


def test_text_behind_person_render():
    cfg = _config(
        template_id="text_behind_person",
        location_tag="杭州学车",
        sub_title="欢迎试学",
        main_title="2980全公开",
        color_theme="classic_blue"
    )
    rendered = render_cover_image(_base(), cfg)
    assert rendered.size == (1080, 1920)
    assert rendered.mode == "RGB"


def test_palettes_registry_exact_colors():
    assert COVER_PALETTES["classic_blue"]["main"] == "#2E7CD6"
    assert COVER_PALETTES["authority_red"]["main"] == "#B91C1C"
    assert COVER_PALETTES["sunset_orange"]["main"] == "#F97316"
    assert COVER_PALETTES["frost_burgundy"]["main"] == "#991B1B"


def test_legacy_palette_ids_resolve_to_comfortable_schemes():
    from app.core.cover_generator import resolve_palette, _LEGACY_PALETTE_ALIASES
    assert _LEGACY_PALETTE_ALIASES["neon_cyber"] == "classic_blue"
    assert _LEGACY_PALETTE_ALIASES["hot_pink_gold"] == "sunset_orange"
    assert resolve_palette("neon_cyber")["main"] == "#2E7CD6"
    assert resolve_palette("hot_pink_gold")["main"] == "#F97316"
    assert resolve_palette("yellow_black")["main"] == "#FACC15"


# ---------------------------------------------------------------------------
# 比例适配
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("size", [(1920, 1080), (800, 800), (1200, 1600), (1080, 1920)])
@pytest.mark.parametrize("mode", ["blur_padding", "center_crop"])
def test_adapt_aspect_ratio_all_modes(size, mode):
    img = Image.new("RGB", size, color=(100, 150, 200))
    adapted = adapt_image_aspect_ratio(img, target_size=(1080, 1920), mode=mode)
    assert adapted.size == (1080, 1920)


# ---------------------------------------------------------------------------
# 6 大模板渲染
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template_id", SIX_TEMPLATES)
def test_render_six_templates_output_1080x1920(template_id):
    rendered = render_cover_image(_base(), _config(template_id=template_id))
    assert rendered.size == (1080, 1920)
    assert rendered.mode == "RGB"


@pytest.mark.parametrize("theme", list(COVER_PALETTES.keys()))
def test_render_six_templates_x_four_palettes(theme):
    for template_id in SIX_TEMPLATES:
        rendered = render_cover_image(_base(), _config(template_id=template_id, color_theme=theme))
        assert rendered.size == (1080, 1920), f"{template_id} x {theme} 渲染失败"


def test_render_legacy_templates_backward_compatible():
    for template_id in LEGACY_TEMPLATE_IDS:
        rendered = render_cover_image(
            _base(), _config(template_id=template_id, color_theme="yellow_black", location_tag="")
        )
        assert rendered.size == (1080, 1920)


def test_render_from_rgba_base_and_empty_texts_fallback():
    rgba_base = Image.new("RGBA", (1080, 1920), color=(30, 30, 30, 255))
    rendered = render_cover_image(rgba_base, _config(location_tag="", main_title="", sub_title=""))
    assert rendered.size == (1080, 1920)


def test_long_title_font_shrink_never_overflows():
    assert _fit_font_size("一" * 6, 168, 6) == 168
    shrunk = _fit_font_size("超" * 25, 168, 6)
    assert 48 <= shrunk < 168
    rendered = render_cover_image(_base(), _config(main_title="超" * 25))
    assert rendered.size == (1080, 1920)


# ---------------------------------------------------------------------------
# 核心视觉算法
# ---------------------------------------------------------------------------
def test_double_stroke_renders_three_layers():
    """贴纸大字三层渲染：区域内必须同时出现 白色描边 / 字芯主色 / 投影像素"""
    canvas = Image.new("RGBA", (900, 360), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = get_font(140, bold=True)
    core = (46, 124, 214, 255)  # classic_blue main
    _draw_double_stroke_text(draw, (120, 90), "武", font, core_fill=core, outer_width=16, inner_width=8)

    region = canvas.crop((0, 0, 900, 360))
    pixels = list(region.getdata())
    has_white = any(p[:3] == (255, 255, 255) for p in pixels)
    has_black = any(p[:3] == (0, 0, 0) for p in pixels)
    has_core = any(abs(p[0] - core[0]) <= 6 and abs(p[1] - core[1]) <= 6 and abs(p[2] - core[2]) <= 6 for p in pixels)
    assert has_white, "缺少白色描边"
    assert has_black, "缺少内层黑描边"
    assert has_core, "缺少字芯主色"


def test_arc_char_positions_symmetric_and_in_bounds():
    text = "武义学车咯"
    positions = _arc_char_positions(text, center=(540, 1260), radius=620, per_char_angle=11.0)
    assert len(positions) == len(text) == 5
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    assert xs[0] < xs[2] < xs[4], "拱形字符应自左向右排布"
    assert ys.index(min(ys)) == 2, "中间字符应位于弧顶（y 最小）"
    for x, y, _rot in positions:
        assert 0 <= x <= 1080
        assert y > 0


def test_fog_mask_linear_gradient():
    mask = _build_fog_mask((100, 400), top_ratio=0.5, max_alpha=235)
    assert mask.mode == "L"
    assert mask.getpixel((50, 0)) == 0
    assert mask.getpixel((50, 200)) == 0
    assert 230 <= mask.getpixel((50, 399)) <= 235
    mid = mask.getpixel((50, 300))
    assert 100 < mid < 235


def test_fog_vignette_brightens_bottom_region():
    base = Image.new("RGBA", (200, 400), (10, 10, 10, 255))
    fogged = _apply_fog_vignette(base, top_ratio=0.5, max_alpha=235)
    assert fogged.mode == "RGBA" and fogged.size == (200, 400)
    top_brightness = sum(fogged.getpixel((100, 10))[:3])
    bottom_brightness = sum(fogged.getpixel((100, 395))[:3])
    assert bottom_brightness > top_brightness + 300, "底部雾化区域应显著变亮（白光羽化生效）"


def test_candidate_frames_cache_hit_avoids_repeated_ffmpeg(tmp_path, monkeypatch):
    """验证当候选帧已存在且有效时，直接复用缓存，绝不重复调用 ffmpeg"""
    from app.core.cover_generator import extract_candidate_frames

    fake_video = tmp_path / "test.mp4"
    fake_video.write_bytes(b"dummy video")
    target_dir = tmp_path / "candidates"
    target_dir.mkdir()

    # 先放好已存在的候选帧
    pre_existing = target_dir / "thumb_candidate_0_50.jpg"
    pre_existing.write_bytes(b"cached frame image")

    # 模拟 subprocess.run，若被调用则记录调用次数
    calls = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        calls.append(cmd)
        import subprocess
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    results = extract_candidate_frames(fake_video, target_dir, timestamps=[0.5])
    assert len(results) == 1
    assert results[0]["filename"] == "thumb_candidate_0_50.jpg"
    # 因为命中缓存，subprocess.run 绝对不应被调用！
    assert len(calls) == 0, "命中候选帧缓存时不应再调用 ffmpeg"


def test_portrait_beauty_and_clarity_enhancement(tmp_path):
    """验证人物美颜与超清增强算法及其在 render_cover_image 中的完整流水线"""
    from PIL import Image
    import numpy as np
    from app.core.cover_generator import enhance_portrait_beauty, render_cover_image
    from app.models.entities import CoverDesignConfig

    # 构造含有人脸肤色区域 (R>G>B, YCbCr 在肤色范围内) 的测试图
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    # 背景为深色
    arr[:100, :] = [30, 40, 50]
    # 人脸肤色区域 (如 R=210, G=160, B=140)
    arr[100:, :] = [210, 160, 140]
    img = Image.fromarray(arr, mode="RGB")

    # 1. 直接测试 enhance_portrait_beauty
    enhanced = enhance_portrait_beauty(img, smooth_level=0.7, whiten_level=0.35, clarity_level=0.5, rosy_level=0.2)
    assert enhanced.size == (200, 200)
    enhanced_arr = np.array(enhanced)

    # 肤色区域应该被提亮并润色
    original_skin_mean = np.mean(arr[100:, :])
    enhanced_skin_mean = np.mean(enhanced_arr[100:, :])
    assert enhanced_skin_mean >= original_skin_mean, "美颜处理后肤色区域平均亮度应当有所提升/通透"

    # 2. 验证 render_cover_image 中携带 enable_portrait_enhancement 正常渲染出图
    config = CoverDesignConfig(
        source="video_frame",
        template_id="text_behind_person",
        location_tag="杭州学车",
        sub_title="欢迎试学",
        main_title="2980全公开",
        enable_portrait_enhancement=True,
        beauty_mode="natural",
        beauty_strength=0.7,
        clarity_strength=0.5
    )
    result_img = render_cover_image(img, config)
    assert isinstance(result_img, Image.Image)
    assert result_img.size == (1080, 1920)


def test_neon_3d_sticker_template():
    """验证新增的荧光绿 3D 贴纸大字模板正常渲染并生成 1080x1920 高清封面"""
    from PIL import Image
    from app.core.cover_generator import render_cover_image, COVER_TEMPLATES_CATALOG, COVER_PALETTES
    from app.models.entities import CoverDesignConfig

    # 1. 验证模板与调色盘已注册
    tpl_ids = [t["id"] for t in COVER_TEMPLATES_CATALOG]
    assert "neon_3d_sticker" in tpl_ids
    assert "neon_lime" in COVER_PALETTES

    # 2. 验证渲染管线成功输出 1080x1920 封面
    base_img = Image.new("RGB", (720, 1280), (120, 150, 180))
    cfg = CoverDesignConfig(
        source="video_frame",
        template_id="neon_3d_sticker",
        location_tag="科二倒车总压线？",
        sub_title="3个黄金点位一把进",
        main_title="零基础听完也能直接过",
        color_theme="neon_lime"
    )
    result = render_cover_image(base_img, cfg)
    assert isinstance(result, Image.Image)
    assert result.size == (1080, 1920)



