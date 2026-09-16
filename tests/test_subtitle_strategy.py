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
    assert strat.subtitle_theme == "viral_gold"
    assert strat.enable_highlight is True
    assert strat.banner_style == "capsule"
    assert strat.broll_pacing == "standard"

    project = CutProject(title="测试工程", talking_head_id="th-123")
    assert project.strategy.subtitle_theme == "viral_gold"
    assert project.strategy.enable_top_banner is True