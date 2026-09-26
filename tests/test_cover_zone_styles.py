"""R3 分区文本样式覆盖（zone_styles）回归测试。

对应 specs/012-video-cover-design plan.md §6（分区编辑与 AI 分区推荐）：
- 实体校验：非法颜色/非法分区键 422（pydantic ValidationError）；scale/offset_y 越界 clamp 后持久化；
- 渲染：三分区覆盖（文字色/描边色/字号/位置）真实改变出图且极端偏移被钳制不越界；
- 契约：POST /cover 携带 zone_styles 合成成功并回显；非法输入返回 422；
- 持久化：工程保存/加载 zone_styles 无损往返。
"""
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
import pydantic

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402
from app.models.entities import (  # noqa: E402
    CoverDesignConfig,
    CoverTextZoneStyle,
    CutProject,
    CutProjectStatus,
)
from app.core.cover_generator import _resolve_zone_styles, render_cover_image  # noqa: E402
from app.native_engine.project_storage import project_storage_service  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# 实体校验与 clamp
# ---------------------------------------------------------------------------
def test_zone_style_rejects_invalid_color_and_key():
    with pytest.raises(pydantic.ValidationError):
        CoverTextZoneStyle(text_color="red")
    with pytest.raises(pydantic.ValidationError):
        CoverTextZoneStyle(text_color="#2E7CD")
    with pytest.raises(pydantic.ValidationError):
        CoverDesignConfig(zone_styles={"footer": CoverTextZoneStyle()})


def test_zone_style_clamps_scale_and_offset():
    zs = CoverTextZoneStyle(scale=9.0, offset_y=-5.0)
    assert zs.scale == 1.4
    assert zs.offset_y == -0.12
    zs2 = CoverTextZoneStyle(scale=0.1, offset_y=3.0)
    assert zs2.scale == 0.6
    assert zs2.offset_y == 0.12
    # 中性默认 = 完全跟随模板与调色盘
    zs3 = CoverTextZoneStyle()
    assert zs3.scale == 1.0 and zs3.offset_y == 0.0 and zs3.text_color is None


def test_resolve_zone_styles_defensive_defaults():
    cfg = CoverDesignConfig(zone_styles={"location": CoverTextZoneStyle(scale=1.3, offset_y=0.05)})
    resolved = _resolve_zone_styles(cfg, 1920)
    assert resolved["location"]["scale"] == pytest.approx(1.3)
    assert resolved["location"]["off_y"] == int(1920 * 0.05)
    # 未覆盖分区保持中性
    assert resolved["main"] == {"scale": 1.0, "off_x": 0, "off_y": 0, "text": None, "stroke": None}
    # 空配置全中性
    empty = _resolve_zone_styles(CoverDesignConfig(), 1920)
    assert all(v["scale"] == 1.0 and v["off_x"] == 0 and v["off_y"] == 0 for v in empty.values())


# ---------------------------------------------------------------------------
# 渲染：覆盖真实生效且极端偏移被钳制
# ---------------------------------------------------------------------------
_BASE = Image.new("RGB", (1080, 1920), (30, 41, 59))


def _render(cfg: CoverDesignConfig) -> Image.Image:
    return render_cover_image(_BASE.copy(), cfg, target_size=(1080, 1920))


def _images_differ(a: Image.Image, b: Image.Image) -> bool:
    return list(a.getdata()) != list(b.getdata())


def _base_config(template_id: str) -> CoverDesignConfig:
    return CoverDesignConfig(
        template_id=template_id,
        location_tag="武义学车",
        main_title="费用全透明",
        sub_title="先看这个",
        color_theme="classic_blue",
    )


# 各模板承载"地域大字"文案的分区（data-model §1.1.1 映射表；R3 修复后 fog 补 main 钩子行、
# editorial 补 location 衬线行，六模板三分区均保证有元素）
_TEMPLATE_COLOR_ZONE = {
    "sticker_double_stroke": "location",
    "split_contrast_bar": "location",
    "rainbow_arc_header": "location",
    "bottom_fog_vignette": "location",
    "angled_impact_stamp": "location",
    "clean_editorial": "location",
}


@pytest.mark.parametrize("template_id", list(_TEMPLATE_COLOR_ZONE.keys()))
def test_zone_overrides_change_render_and_clamp(template_id):
    base_out = _render(_base_config(template_id))
    assert base_out.size == (1080, 1920)

    # 文字色覆盖：地域大字所在分区改纯黄，出图必然改变
    color_zone = _TEMPLATE_COLOR_ZONE[template_id]
    colored = _base_config(template_id)
    colored.zone_styles = {color_zone: CoverTextZoneStyle(text_color="#FACC15")}
    out_colored = _render(colored)
    assert out_colored.size == (1080, 1920)
    assert _images_differ(base_out, out_colored), f"{template_id}: 文字色覆盖未生效"

    # 极端偏移/字号越界：服务端 clamp 后正常出图，绝不崩溃、不越界
    extreme = _base_config(template_id)
    extreme.zone_styles = {
        "location": CoverTextZoneStyle(offset_y=0.5, scale=9.0),
        "main": CoverTextZoneStyle(offset_y=-0.5, scale=0.1),
        "sub": CoverTextZoneStyle(offset_y=0.12),
    }
    out_extreme = _render(extreme)
    assert out_extreme.size == (1080, 1920)
    assert _images_differ(base_out, out_extreme), f"{template_id}: 偏移钳制后未体现在出图"


def test_zone_offset_zero_equals_default_render():
    cfg = _base_config("sticker_double_stroke")
    neutral = _base_config("sticker_double_stroke")
    neutral.zone_styles = {"main": CoverTextZoneStyle()}
    # 中性覆盖（全默认值）渲染结果与无覆盖一致
    assert not _images_differ(_render(cfg), _render(neutral))


# ---------------------------------------------------------------------------
# POST /cover 契约与持久化往返
# ---------------------------------------------------------------------------
def _make_project() -> CutProject:
    proj = CutProject(
        id="test_proj_zone_001",
        title="科目二倒车入库秘籍",
        talking_head_id="th_zone_001",
        task_dir="tasks/test_task_zone_001",
        status=CutProjectStatus.DRAFT,
    )
    project_storage_service.save_project(proj)
    return proj


def _base64_image() -> str:
    import base64
    buf = io.BytesIO()
    Image.new("RGB", (1080, 1920), color=(30, 41, 59)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_cover_api_accepts_zone_styles_and_clamps(tmp_path):
    proj = _make_project()
    payload = {
        "source": "custom_upload",
        "template_id": "sticker_double_stroke",
        "location_tag": "武义学车",
        "main_title": "费用全透明",
        "sub_title": "先看这个",
        "image_base64": _base64_image(),
        "zone_styles": {
            "location": {"text_color": "#2E7CD6", "stroke_color": "#FFFFFF", "scale": 9.0, "offset_y": -0.03},
            "main": {"text_color": "#FFFFFF", "stroke_color": "#000000", "scale": 1.0, "offset_y": 0.05},
            "sub": {},
        },
    }
    res = client.post(f"/api/v1/projects/{proj.id}/cover", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["cover_config"]["zone_styles"]["location"]["scale"] == 1.4  # 越界 clamp 后持久化/回显
    assert data["cover_config"]["zone_styles"]["location"]["offset_y"] == -0.03
    # 空 dict 被实体补全为中性默认 = 完全跟随模板与调色盘
    assert data["cover_config"]["zone_styles"]["sub"]["scale"] == 1.0
    assert data["cover_config"]["zone_styles"]["sub"]["text_color"] is None

    # 封面真实落盘
    from app.core.config import STORAGE_DIR
    loaded = project_storage_service.get_by_project_id(proj.id)
    assert loaded.cover_config is not None
    assert loaded.cover_config.zone_styles["location"].text_color == "#2E7CD6"
    cover_file = (STORAGE_DIR.parent / loaded.cover_image_path).resolve()
    assert cover_file.exists()
    with Image.open(cover_file) as img:
        assert img.size == (1080, 1920)


def test_cover_api_rejects_invalid_zone_styles(tmp_path):
    proj = _make_project()
    bad_color = {
        "source": "custom_upload",
        "template_id": "sticker_double_stroke",
        "main_title": "测试",
        "image_base64": _base64_image(),
        "zone_styles": {"location": {"text_color": "not-a-color"}},
    }
    res = client.post(f"/api/v1/projects/{proj.id}/cover", json=bad_color)
    assert res.status_code == 422

    bad_key = dict(bad_color, zone_styles={"banner": {"scale": 1.1}})
    res2 = client.post(f"/api/v1/projects/{proj.id}/cover", json=bad_key)
    assert res2.status_code == 422


def test_zone_styles_persistence_roundtrip():
    proj = _make_project()
    proj.cover_config = CoverDesignConfig(
        template_id="split_contrast_bar",
        location_tag="杭州学车",
        main_title="明码标价",
        zone_styles={
            "location": CoverTextZoneStyle(text_color="#FDE047", stroke_color="#000000", scale=1.25, offset_y=0.02),
            "main": CoverTextZoneStyle(scale=0.9),
        },
    )
    project_storage_service.save_project(proj)
    loaded = project_storage_service.get_by_project_id(proj.id)
    assert loaded is not None and loaded.cover_config is not None
    zs = loaded.cover_config.zone_styles
    assert set(zs.keys()) == {"location", "main"}
    assert zs["location"].text_color == "#FDE047"
    assert zs["location"].stroke_color == "#000000"
    assert zs["location"].scale == 1.25
    assert zs["location"].offset_y == 0.02
    assert zs["main"].scale == 0.9 and zs["main"].text_color is None


def test_doodle_offsets_rendering_and_roundtrip():
    """验证非文字标贴（双三角 △ △、射线光束）上下左右 2D 全向拖拽偏移能够真实改变出图且持久化无损往返"""
    cfg_base = CoverDesignConfig(
        template_id="neon_3d_sticker",
        location_tag="女生学车更难？",
        sub_title="男女学员真实表现对比",
        main_title="别再凭性别下结论",
    )
    img_base = _render(cfg_base)

    cfg_moved = CoverDesignConfig(
        template_id="neon_3d_sticker",
        location_tag="女生学车更难？",
        sub_title="男女学员真实表现对比",
        main_title="别再凭性别下结论",
        doodle_offsets={
            "triangles": {"x": 0.08, "y": 0.05},
            "rays_right": {"x": -0.05, "y": 0.03}
        }
    )
    img_moved = _render(cfg_moved)
    assert _images_differ(img_base, img_moved), "doodle_offsets 偏移后出图必须发生像素级真实差异"

    # 持久化往返验证
    proj = _make_project()
    proj.cover_config = cfg_moved
    project_storage_service.save_project(proj)
    loaded = project_storage_service.get_by_project_id(proj.id)
    assert loaded is not None and loaded.cover_config is not None
    assert loaded.cover_config.doodle_offsets["triangles"] == {"x": 0.08, "y": 0.05}
    assert loaded.cover_config.doodle_offsets["rays_right"] == {"x": -0.05, "y": 0.03}

