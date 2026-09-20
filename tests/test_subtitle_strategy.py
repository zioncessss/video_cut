import pytest
from pathlib import Path
from app.native_engine.asr_runner import asr_runner
from app.native_engine.subtitle_styler import generate_ass_file, hex_to_ass_color, format_timestamp_ass
from app.models.entities import EditingStrategy, CutProject

def test_split_into_readable_segments():
    long_segments = [
        {
            "start_time": 0.0,
            "end_time": 6.0,
            "raw_text": "同学们好，今天带大家看看我们自建的五万平标准化训练场，设施设备全部一应俱全。"
        }
    ]
    refined = asr_runner.split_into_readable_segments(long_segments, max_chars=14)
    assert len(refined) >= 2
    for seg in refined:
        assert len(seg["raw_text"]) <= 16
        assert seg["start_time"] < seg["end_time"]
    assert refined[0]["start_time"] == 0.0
    assert refined[-1]["end_time"] == 6.0

def test_hex_to_ass_color():
    assert hex_to_ass_color("#FACC15") == "&H0015CCFA&"
    assert hex_to_ass_color("#10B981") == "&H0081B910&"
    assert hex_to_ass_color("") == "&H0015CCFA&"

def test_format_timestamp_ass():
    assert format_timestamp_ass(0.0) == "0:00:00.00"
    assert format_timestamp_ass(65.456) == "0:01:05.46"

def test_generate_ass_file(tmp_path):
    subtitles = [
        {
            "start_time": 1.0,
            "end_time": 3.5,
            "raw_text": "专业金牌教练手把手教学，科目二倒库轻松一把过。",
            "corrected_text": "专业金牌教练手把手教学，科目二倒库轻松一把过。",
            "matched_keywords": ["科目二", "倒库"]
        }
    ]
    strat = {
        "subtitle_theme": "viral_gold",
        "enable_highlight": True,
        "highlight_color": "#FACC15",
        "highlight_scale": True,
        "custom_highlight_words": ["金牌教练"]
    }
    ass_path = tmp_path / "test.ass"
    out = generate_ass_file(subtitles, ass_path, strategy=strat)
    assert out.exists()
    content = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Dialogue: 0,0:00:01.00,0:00:03.50,Default" in content
    # 关键词包含变色标签
    assert r"\c&H0015CCFA&" in content
    assert "科目二" in content
    assert "金牌教练" in content

def test_editing_strategy_model():
    strat = EditingStrategy()
    assert strat.subtitle_theme == "glow_gold"
    assert strat.enable_highlight is True
    assert strat.banner_style == "capsule"
    assert strat.banner_size == "medium"
    assert strat.banner_position_y == 6
    assert strat.watermark_size == "medium"
    assert strat.watermark_position == "top_right"
    assert strat.watermark_position_y is None
    assert strat.broll_pacing == "standard"

    project = CutProject(title="测试工程", talking_head_id="th-123")
    assert project.strategy.subtitle_theme == "glow_gold"
    # 005 起：新建工程默认关闭横幅与水印（成片评审后可手动开启）
    assert project.strategy.enable_top_banner is False
    assert project.strategy.enable_watermark is False
    assert project.strategy.banner_size == "medium"

def test_banner_and_watermark_custom_strategy():
    strat = EditingStrategy(
        banner_size="large",
        banner_position_x=40,
        banner_position_y=15,
        banner_font_size=56,
        watermark_size="small",
        watermark_position="bottom_left",
        watermark_position_x=12,
        watermark_position_y=88,
        watermark_font_size=28,
        subtitle_font_size=60,
        subtitle_position_x=45,
        subtitle_position_y=75
    )
    assert strat.banner_size == "large"
    assert strat.banner_position_x == 40
    assert strat.banner_position_y == 15
    assert strat.banner_font_size == 56
    assert strat.watermark_size == "small"
    assert strat.watermark_position == "bottom_left"
    assert strat.watermark_position_x == 12
    assert strat.watermark_position_y == 88
    assert strat.watermark_font_size == 28
    assert strat.subtitle_font_size == 60
    assert strat.subtitle_position_x == 45
    assert strat.subtitle_position_y == 75

def test_generate_ass_file_2d_position_and_flexible_font(tmp_path):
    subtitles = [
        {
            "start_time": 0.5,
            "end_time": 2.5,
            "raw_text": "同学们好，今天带大家练科目二。",
            "matched_keywords": ["科目二"]
        }
    ]
    strat = {
        "subtitle_theme": "glow_gold",
        "subtitle_font_size": 68,
        "subtitle_position_x": 42,
        "subtitle_position_y": 70,
        "enable_highlight": True,
        "highlight_color": "#FACC15",
    }
    ass_path = tmp_path / "test_2d.ass"
    out = generate_ass_file(subtitles, ass_path, strategy=strat)
    assert out.exists()
    content = ass_path.read_text(encoding="utf-8")
    
    # 验证自定义 68px 字号写入样式与默认华文中宋
    assert "STZhongsong,68," in content
    # 验证 2D 坐标 (1080 * 0.42 = 453, 1920 * 0.70 = 1344)
    assert r"\an5\pos(453,1344)" in content

def test_generate_ass_reads_highlight_words_source(tmp_path):
    """高亮渲染数据源切换：优先 highlight_words（三源结构），缺失时回退 matched_keywords。
    断言的是行内高亮标记（{\\c&H..&\\b1\\fscx110\\fscy110}词）而非词本身。"""
    base_text = "从今年九月份开始湖州驾校迎来大改革"
    strat = {"subtitle_theme": "glow_gold", "enable_highlight": True, "highlight_color": "#FACC15", "highlight_scale": True}
    hl_marker = r"{\c&H0015CCFA&\b1\fscx110\fscy110}"

    # 1) highlight_words 存在：不在 matched_keywords 里的 AI/手动词也被高亮
    subs_new = [{
        "start_time": 0.0, "end_time": 3.0,
        "raw_text": base_text, "corrected_text": base_text,
        "matched_keywords": ["湖州驾校"],
        "highlight_words": [
            {"word": "九月份", "source": "ai"},
            {"word": "大改革", "source": "manual"},
            {"word": "湖州驾校", "source": "glossary"}
        ]
    }]
    out = generate_ass_file(subs_new, tmp_path / "new.ass", strategy=strat)
    content = out.read_text(encoding="utf-8")
    for w in ("九月份", "大改革", "湖州驾校"):
        assert hl_marker + w in content, f"highlight_words 来源的词应被行内高亮: {w}"

    # 2) highlight_words 缺失：回退 matched_keywords 兼容旧数据
    subs_old = [{
        "start_time": 0.0, "end_time": 3.0,
        "raw_text": base_text, "corrected_text": base_text,
        "matched_keywords": ["湖州驾校"]
    }]
    out2 = generate_ass_file(subs_old, tmp_path / "old.ass", strategy=strat)
    content2 = out2.read_text(encoding="utf-8")
    assert hl_marker + "湖州驾校" in content2
    assert hl_marker + "九月份" not in content2, "回退模式下 AI 词不应被高亮"