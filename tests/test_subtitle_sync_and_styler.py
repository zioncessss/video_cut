import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory, SubtitleSegment, EditingStrategy
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.native_engine.subtitle_styler import generate_ass_file

client = TestClient(app)

def test_subtitle_put_persistence_roundtrip(tmp_path):
    """验证通过 PUT /subtitles 接口提交修改后，SQLite 权威库能够正确落盘并保留 is_manual_edited 标记"""
    fake_th_file = tmp_path / "talking_head_sync.mp4"
    fake_th_file.write_bytes(b"fake_talking_head_video_stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "talking_head_sync.mp4", fake_th_file)

    try:
        # 创建工程
        res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        assert res.status_code == 200
        proj = res.json()
        pid = proj["id"]
        assert len(proj["subtitles"]) > 0

        # 修改字幕并打上 is_manual_edited: True
        subs = proj["subtitles"]
        subs[0]["corrected_text"] = "在杭州考驾照多少钱？"
        subs[0]["is_manual_edited"] = True

        put_res = client.put(
            f"/api/v1/projects/{pid}/subtitles",
            json={"subtitles": subs}
        )
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert put_data["subtitles"][0]["corrected_text"] == "在杭州考驾照多少钱？"
        assert put_data["subtitles"][0]["is_manual_edited"] is True

        # 从 SQLite 重新拉取，确保持久化有效
        get_res = client.get(f"/api/v1/projects/{pid}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["subtitles"][0]["corrected_text"] == "在杭州考驾照多少钱？"
        assert get_data["subtitles"][0]["is_manual_edited"] is True

    finally:
        storage_service.delete_material(th.id)

def test_ass_font_size_and_geometry_parity(tmp_path):
    """
    验证 ASS 字幕生成器在 1080x1920 竖屏画布下，
    生成的 Fontsize、margin_h、margin_v 与策略参数严格保持 1:1 几何映射。
    """
    subtitles = [
        {
            "id": "s1",
            "start_time": 1.0,
            "end_time": 3.0,
            "raw_text": "在杭州考驾照多少钱",
            "corrected_text": "在杭州考驾照多少钱",
            "highlight_words": [{"word": "杭州", "color": "#38BDF8"}],
        }
    ]

    ass_file = tmp_path / "test.ass"

    # 测试标准中号 72px，宽度 90%，垂直位置 82%
    strategy_medium = {
        "subtitle_theme": "glow_gold",
        "subtitle_font_size": 72,
        "subtitle_width_percent": 90,
        "subtitle_position_x": 50,
        "subtitle_position_y": 82,
        "enable_highlight": True,
        "highlight_color": "#FACC15",
    }

    generate_ass_file(subtitles, ass_file, strategy=strategy_medium)
    content = ass_file.read_text(encoding="utf-8")

    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "Style: Default,Microsoft YaHei,72," in content
    # margin_h = 1080 * (100 - 90) / 200 = 54
    assert ",54,54," in content
    # \pos(1080 * 50 / 100, 1920 * 82 / 100) = \pos(540,1574)
    assert r"\pos(540,1574)" in content

    # 测试大号 86px，宽度 80%
    strategy_large = {
        "subtitle_theme": "cinema_shadow",
        "subtitle_font_size": 86,
        "subtitle_width_percent": 80,
        "subtitle_position_x": 50,
        "subtitle_position_y": 80,
    }
    generate_ass_file(subtitles, ass_file, strategy=strategy_large)
    content_large = ass_file.read_text(encoding="utf-8")
    assert "Style: Default,Microsoft YaHei,86," in content_large
    # margin_h = 1080 * (100 - 80) / 200 = 108
    assert ",108,108," in content_large
    # \pos(540, 1536)
    assert r"\pos(540,1536)" in content_large
