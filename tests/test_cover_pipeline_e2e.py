import io
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.models.entities import CutProject, CutProjectStatus, MaterialCategory
from app.native_engine.project_storage import project_storage_service
from app.native_engine.storage import storage_service

client = TestClient(app)

def test_get_cover_templates_api():
    """验证 GET /api/v1/editor/cover-templates 契约：6 大实战模板 + 4 套调色盘 + 安全区"""
    res = client.get("/api/v1/editor/cover-templates")
    assert res.status_code == 200
    data = res.json()["data"]
    template_ids = [t["id"] for t in data["templates"]]
    assert template_ids == [
        "sticker_double_stroke",
        "split_contrast_bar",
        "rainbow_arc_header",
        "bottom_fog_vignette",
        "angled_impact_stamp",
        "clean_editorial",
        "text_behind_person",
        "neon_3d_sticker",
    ]
    first = data["templates"][0]
    for key in ("name", "category", "badge", "sample_preview", "description", "supported_themes"):
        assert key in first, f"模板元数据缺少 {key}"

    palette_ids = {p["id"] for p in data["palettes"]}
    assert palette_ids == {"classic_blue", "authority_red", "sunset_orange", "frost_burgundy", "neon_lime"}
    for p in data["palettes"]:
        assert p["main"].startswith("#") and p["sub"].startswith("#") and p["accent"].startswith("#")

    # 学车特点库（底部钩子标题素材库，storage/glossary.json cover_hooks 唯一事实源）
    assert isinstance(data["cover_hooks"], list) and len(data["cover_hooks"]) >= 10
    assert "费用全透明" in data["cover_hooks"]

    assert "safe_zones" in data
    assert data["safe_zones"]["douyin"]["bottom"] == 0.18
    assert data["safe_zones"]["xiaohongshu"]["aspect"] == "3:4"

def test_set_and_render_cover_api(tmp_path):
    """验证 POST /api/v1/projects/{project_id}/cover 的多模板渲染与存储落盘"""
    # 创建一个测试工程
    proj = CutProject(
        id="test_proj_cover_001",
        title="科目二倒车入库秘籍",
        talking_head_id="th_001",
        task_dir=f"tasks/test_task_{proj_id}" if "proj_id" in locals() else "tasks/test_task_cov1",
        status=CutProjectStatus.DRAFT
    )
    project_storage_service.save_project(proj)

    # 创建一个模拟底图 (1080x1920)
    base_img = Image.new("RGB", (1080, 1920), color=(30, 41, 59))
    buf = io.BytesIO()
    base_img.save(buf, format="JPEG")
    import base64
    b64_img = base64.b64encode(buf.getvalue()).decode("ascii")

    # 1. 设置金牌大字报模板
    payload = {
        "source": "custom_upload",
        "template_id": "gold_bold",
        "main_title": "自建5万平训练场",
        "sub_title": "科二科三一把过",
        "image_base64": b64_img,
        "show_safe_zone": False
    }
    res = client.post(f"/api/v1/projects/{proj.id}/cover", json=payload)
    assert res.status_code == 200
    resp_data = res.json()["data"]
    assert resp_data["cover_image_path"].endswith("cover.jpg") or "cover_" in resp_data["cover_image_path"]
    assert resp_data["cover_config"]["template_id"] == "gold_bold"
    assert resp_data["cover_config"]["main_title"] == "自建5万平训练场"

    # 验证工程落库状态
    loaded = project_storage_service.get_by_project_id(proj.id)
    assert loaded is not None
    assert loaded.cover_config is not None
    assert loaded.cover_config.template_id == "gold_bold"

    # 2. 切换为爆款色块模板
    payload2 = {
        "source": "custom_upload",
        "template_id": "color_badge",
        "main_title": "教练私藏避坑绝招",
        "sub_title": "零基础也能学会",
        "image_base64": b64_img
    }
    res2 = client.post(f"/api/v1/projects/{proj.id}/cover", json=payload2)
    assert res2.status_code == 200
    assert res2.json()["data"]["cover_config"]["template_id"] == "color_badge"

    loaded2 = project_storage_service.get_by_project_id(proj.id)
    assert loaded2.cover_config.template_id == "color_badge"

    # 3. 切换为 6 大实战新模板（双层描边贴纸大字）并携带地域词锚点
    payload3 = {
        "source": "custom_upload",
        "template_id": "sticker_double_stroke",
        "location_tag": "武义学车",
        "main_title": "费用全透明",
        "sub_title": "先看这个",
        "color_theme": "classic_blue",
        "font_family": "heavy_gothic",
        "image_base64": b64_img
    }
    res3 = client.post(f"/api/v1/projects/{proj.id}/cover", json=payload3)
    assert res3.status_code == 200
    data3 = res3.json()["data"]
    assert data3["cover_config"]["template_id"] == "sticker_double_stroke"
    assert data3["cover_config"]["location_tag"] == "武义学车"
    assert data3["cover_config"]["color_theme"] == "classic_blue"

    # 封面图真实落盘且为 1080x1920
    loaded3 = project_storage_service.get_by_project_id(proj.id)
    assert loaded3.cover_config.location_tag == "武义学车"
    from app.core.config import STORAGE_DIR
    cover_file = (STORAGE_DIR.parent / loaded3.cover_image_path).resolve()
    assert cover_file.exists(), f"封面文件未落盘: {loaded3.cover_image_path}"
    with Image.open(cover_file) as cov_img:
        assert cov_img.size == (1080, 1920)


def test_project_suggested_cover_titles_roundtrip():
    """验证 AI 伴随封面文案（含地域词）在工程存储中的完整持久化"""
    proj = CutProject(
        id="test_proj_sugg_cov",
        title="武义学车避坑指南",
        talking_head_id="th_sugg_test",
        status=CutProjectStatus.DRAFT,
        suggested_cover_titles=[
            {
                "location_tag": "武义学车",
                "main_title": "学车避坑指南",
                "sub_title": "一口价全包",
                "rationale": "直击价格痛点并锚定同城流量",
                "style_hint": "sticker_double_stroke"
            }
        ]
    )
    project_storage_service.save_project(proj)

    loaded = project_storage_service.get_by_project_id(proj.id)
    assert loaded is not None
    assert len(loaded.suggested_cover_titles) == 1
    item = loaded.suggested_cover_titles[0]
    assert item.location_tag == "武义学车"
    assert item.main_title == "学车避坑指南"
    assert item.style_hint == "sticker_double_stroke"

def test_upload_cover_image_api():
    """验证 POST /api/v1/projects/{project_id}/cover/upload 的自适应上传"""
    proj = CutProject(
        id="test_proj_upload_cov",
        title="自定义图片上传测试",
        talking_head_id="th_upload_test",
        status=CutProjectStatus.DRAFT
    )
    project_storage_service.save_project(proj)

    # 创建一个 16:9 横屏图片 (1920x1080)
    landscape_img = Image.new("RGB", (1920, 1080), color=(16, 185, 129))
    buf = io.BytesIO()
    landscape_img.save(buf, format="JPEG")
    buf.seek(0)

    # 1. 以 blur_padding 模式上传
    files = {"file": ("test_cover.jpg", buf, "image/jpeg")}
    res = client.post(
        f"/api/v1/projects/{proj.id}/cover/upload?aspect_mode=blur_padding",
        files=files
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["width"] == 1080
    assert data["height"] == 1920
    assert data["aspect_mode"] == "blur_padding"

    # 2. 以 center_crop 模式上传
    buf2 = io.BytesIO()
    landscape_img.save(buf2, format="JPEG")
    buf2.seek(0)
    files2 = {"file": ("test_crop.jpg", buf2, "image/jpeg")}
    res2 = client.post(
        f"/api/v1/projects/{proj.id}/cover/upload?aspect_mode=center_crop",
        files=files2
    )
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["width"] == 1080
    assert data2["height"] == 1920
    assert data2["aspect_mode"] == "center_crop"


def test_render_project_optional_cover(tmp_path, monkeypatch):
    """验证 POST /api/v1/editor/{project_id}/render 的封面可选参数 (include_cover & embed_cover_as_first_frame)"""
    from app.models.entities import EditingStrategy, Material

    # 1. 注册测试素材与工程
    mat = storage_service.save_material(
        MaterialCategory.TALKING_HEAD,
        "talking_head.mp4",
        b"dummy mp4 content"
    )
    mat_id = mat.id

    proj_id = "test_proj_render_opt"
    task_dir_path = tmp_path / "task_opt"
    task_dir_path.mkdir(parents=True, exist_ok=True)
    proj = CutProject(
        id=proj_id,
        title="封面可选导出测试",
        talking_head_id=mat_id,
        task_dir="tasks/task_opt",
        strategy=EditingStrategy(embed_cover_as_first_frame=False),
        status=CutProjectStatus.DRAFT
    )
    project_storage_service.save_project(proj)

    # Mock composer.compose_jl_cut 生成虚拟成片
    from app.native_engine.ffmpeg_filter import composer
    def fake_compose(*args, **kwargs):
        out_p = kwargs["output_path"]
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(b"rendered video content")
        return True

    monkeypatch.setattr(composer, "compose_jl_cut", fake_compose)

    # 测试 A: 当 include_cover=False 时，不生成也不导出封面
    dest_dir = tmp_path / "my_exports_nocover"
    dest_dir.mkdir(parents=True, exist_ok=True)

    res_nocover = client.post(
        f"/api/v1/editor/{proj_id}/render?include_cover=false&export_dir={str(dest_dir)}"
    )
    assert res_nocover.status_code == 200
    # 验证导出的文件夹中只有 mp4，没有 cover.jpg
    exported_files = list(dest_dir.glob("*"))
    assert any(f.name.endswith(".mp4") for f in exported_files)
    assert not any("cover" in f.name.lower() for f in exported_files), "include_cover=false 时不应导出封面图片"

    # 测试 B: 当 include_cover=True 且配置了 cover_config 时，必须使用最新 cover_config 渲染封面并输出到导出目录
    from app.models.entities import CoverDesignConfig
    proj.cover_config = CoverDesignConfig(
        template_id="sticker_double_stroke",
        location_tag="杭州学车",
        main_title="最新一口价",
        sub_title="欢迎试学",
        color_theme="classic_blue"
    )
    project_storage_service.save_project(proj)

    dest_dir_with_cover = tmp_path / "my_exports_withcover"
    dest_dir_with_cover.mkdir(parents=True, exist_ok=True)

    res_cover = client.post(
        f"/api/v1/editor/{proj_id}/render?include_cover=true&embed_cover_as_first_frame=false&export_dir={str(dest_dir_with_cover)}"
    )
    assert res_cover.status_code == 200
    exported_with_cov = list(dest_dir_with_cover.glob("*"))
    assert any(f.name.endswith(".mp4") for f in exported_with_cov)
    assert any("cover" in f.name.lower() for f in exported_with_cov), "include_cover=true 时必须同步导出封面文件"

