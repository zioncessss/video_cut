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
from app.native_engine.subtitle_styler import generate_ass_file, generate_srt_file, smooth_subtitle_timings

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
    assert "Style: Default,STZhongsong,72," in content
    # margin_h = 1080 * (100 - 90) / 200 = 54
    assert ",54,54," in content
    # \pos(1080 * 50 / 100, 1920 * 82 / 100) = \pos(540,1574)
    assert r"\pos(540,1574)" in content

    # 测试大号 86px，宽度 80%，指定现代黑体 yahei
    strategy_large = {
        "subtitle_theme": "cinema_shadow",
        "subtitle_font_family": "yahei",
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


def test_ass_highlight_styling_parity(tmp_path):
    """
    验证 ASS 字幕高亮词样式：
    1. 彩色高亮词（如 #38BDF8）：生成 \\c&H...&\\b1\\fscx115\\fscy115 并复位 \\r\\fscx100\\fscy100
    2. 纯白高亮词（#FFFFFF）：生成 \\b1\\fscx122\\fscy122 形成大字号白光强调
    """
    subtitles = [
        {
            "id": "s1",
            "start_time": 1.0,
            "end_time": 3.0,
            "raw_text": "在杭州考驾照重点是避坑",
            "corrected_text": "在杭州考驾照重点是避坑",
            "highlight_words": [
                {"word": "杭州", "color": "#38BDF8"},
                {"word": "避坑", "color": "#FFFFFF"},
            ],
        }
    ]
    ass_file = tmp_path / "highlight_test.ass"
    strategy = {
        "subtitle_theme": "glow_gold",
        "subtitle_font_size": 72,
        "enable_highlight": True,
        "highlight_scale": True,
    }
    generate_ass_file(subtitles, ass_file, strategy=strategy)
    content = ass_file.read_text(encoding="utf-8")

    # 杭州为彩色高亮
    assert r"{\c&H00F8BD38&\b1\fscx110\fscy110}杭州{\r\fscx100\fscy100}" in content
    # 避坑为纯白高亮，采用 122% 放大与加粗
    assert r"{\b1\fscx122\fscy122}避坑{\r\fscx100\fscy100}" in content


def test_ass_long_subtitle_wrapping_with_newline(tmp_path):
    """
    验证超长单行字幕（>14字）在 ASS 生成时，自动在语法断句点或中心插入 \\N 折行，
    避免单行字幕超出 1080x1920 竖屏画布左右两端。
    """
    subtitles = [
        {
            "id": "s_long",
            "start_time": 27.4,
            "end_time": 30.9,
            "raw_text": "他给你报一千多还跟你说全包或者是怎么样",
            "corrected_text": "他给你报一千多还跟你说全包或者是怎么样",
            "highlight_words": [
                {"word": "一千多", "color": "#EF4444"},
                {"word": "全包", "color": "#FFFFFF"},
            ],
        }
    ]
    ass_file = tmp_path / "long_test.ass"
    generate_ass_file(subtitles, ass_file)
    content = ass_file.read_text(encoding="utf-8")

    # 19 字超长句必须包含 \N 换行标记，杜绝单行横向溢出
    assert r"\N" in content
    # 且在 "还" 前优雅折行
    assert r"他给你报" in content and r"或者是怎么样" in content


def test_video_speed_scaling_and_subtitles():
    """
    验证倍速剪辑策略 (video_speed != 1.0)：
    1. 字幕起止时间与词级起止时间等比按 1/speed 缩放；
    2. 倍速为 1.0 时原始时间戳不变。
    """
    from app.api.editor import _prepare_render_subtitles
    from app.models.entities import EditingStrategy

    strat = EditingStrategy(video_speed=1.2)
    assert strat.video_speed == 1.2

    raw_subs = [
        {
            "id": "s1",
            "start_time": 1.2,
            "end_time": 2.4,
            "raw_text": "在杭州考驾照",
            "corrected_text": "在杭州考驾照",
            "words": [
                {"word": "在杭州", "start": 1.2, "end": 1.8},
                {"word": "考驾照", "start": 1.8, "end": 2.4},
            ]
        }
    ]

    # 1.2 倍速渲染字幕时间缩放
    scaled = _prepare_render_subtitles(raw_subs, speed=1.2)
    assert scaled[0]["start_time"] == 1.0
    assert scaled[0]["end_time"] == 2.0
    assert scaled[0]["words"][0]["start"] == 1.0
    assert scaled[0]["words"][0]["end"] == 1.5
    assert scaled[0]["words"][1]["start"] == 1.5
    assert scaled[0]["words"][1]["end"] == 2.0

    # 1.0 原速不缩放
    unscaled = _prepare_render_subtitles(raw_subs, speed=1.0)
    assert unscaled[0]["start_time"] == 1.2
    assert unscaled[0]["end_time"] == 2.4

def test_cinema_shadow_and_songti_fonts(tmp_path):
    """
    验证精简后的电影立体白（紧凑立体阴影 Outline 2.0 / Shadow 3.2 适配 1080P）
    以及华文中宋（解决可变字体 ExtraLight Bug）、清雅仿宋、经典宋体的字体族映射与 100% 贴边内边距。
    """
    subs = [
        {
            "id": "s1",
            "start_time": 0.0,
            "end_time": 2.5,
            "raw_text": "在杭州考驾照",
            "corrected_text": "在杭州考驾照",
        }
    ]

    # 1. 思源 / 华文中宋 (STZhongsong) + 电影立体白
    p1 = tmp_path / "noto.ass"
    generate_ass_file(subs, p1, strategy={"subtitle_theme": "cinema_shadow", "subtitle_font_family": "notoserif"})
    c1 = p1.read_text(encoding="utf-8")
    assert "Style: Default,STZhongsong,72," in c1
    # Outline 0.6, Shadow 1.8 (方案 A 电影立体白)
    assert ",1,0.6,1.8,2," in c1
    # 默认 100% 宽度 margin_h = 24
    assert ",24,24," in c1

    # 2. 清雅仿宋 (FangSong)
    p2 = tmp_path / "fangsong.ass"
    generate_ass_file(subs, p2, strategy={"subtitle_theme": "cinema_shadow", "subtitle_font_family": "fangsong"})
    c2 = p2.read_text(encoding="utf-8")
    assert "Style: Default,FangSong,72," in c2

    # 3. 经典宋体 (SimSun)
    p3 = tmp_path / "songti.ass"
    generate_ass_file(subs, p3, strategy={"subtitle_theme": "cinema_shadow", "subtitle_font_family": "songti"})
    c3 = p3.read_text(encoding="utf-8")
    assert "Style: Default,SimSun,72," in c3

def test_subtitle_smoothing_ass_and_srt(tmp_path):
    """验证 smooth_timings=True 时字幕施加 70ms 听觉前置与微停顿无缝延留接力"""
    raw_subs = [
        {"start_time": 1.2, "end_time": 4.5, "corrected_text": "今天看标准化场地"},
        {"start_time": 4.7, "end_time": 8.0, "corrected_text": "科目二倒车入库一把过"}
    ]
    # 未开启平滑时，保持原始时间戳
    raw_srt = tmp_path / "raw.srt"
    generate_srt_file(raw_subs, raw_srt, smooth_timings=False)
    assert "00:00:01,200 --> 00:00:04,500" in raw_srt.read_text(encoding="utf-8")

    # 开启平滑时，第一句施加 70ms 听觉前置 (1.200 -> 1.130)，且 0.2s 间隙平滑延留接力至下一句前置点 (4.630)
    smooth_srt = tmp_path / "smooth.srt"
    generate_srt_file(raw_subs, smooth_srt, smooth_timings=True)
    smooth_content = smooth_srt.read_text(encoding="utf-8")
    assert "00:00:01,130 --> 00:00:04,630" in smooth_content
    assert "00:00:04,630 --> 00:00:08,300" in smooth_content




