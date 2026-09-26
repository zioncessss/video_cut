import pytest
import sqlite3
import json
from pathlib import Path
from app.core.compliance_sanitizer import compliance_sanitizer
from app.native_engine.subtitle_styler import generate_ass_file

def test_full_pipeline_with_real_subtitles(tmp_path):
    # 模拟真实口播剧本字幕，包含用户指定的全部高危场景
    raw_subtitles = [
        {
            "start_time": 0.0,
            "end_time": 2.0,
            "raw_text": "在杭州考一个驾照要多少钱",
            "corrected_text": "在杭州考一个驾照要多少钱",
            "highlight_words": [
                {"word": "杭州", "color": "#38BDF8", "category": "location"},
                {"word": "多少钱", "color": "#EF4444", "category": "price"}
            ]
        },
        {
            "start_time": 2.0,
            "end_time": 4.5,
            "raw_text": "首先呢就是四科考试费和体检费",
            "corrected_text": "首先呢就是四科考试费和体检费",
            "highlight_words": [
                {"word": "四科考试费", "color": "#EF4444", "category": "price"},
                {"word": "体检费", "color": "#EF4444", "category": "price"}
            ]
        },
        {
            "start_time": 4.5,
            "end_time": 7.0,
            "raw_text": "我们现在学车通通一口价，最快最便宜",
            "corrected_text": "我们现在学车通通一口价，最快最便宜",
            "highlight_words": [
                {"word": "一口价", "color": "#FACC15", "category": "emphasis"}
            ]
        },
        {
            "start_time": 7.0,
            "end_time": 9.5,
            "raw_text": "点个红心加关注，评论区找我聊",
            "corrected_text": "点个红心加关注，评论区找我聊",
            "highlight_words": []
        }
    ]

    # 1. 预检检测
    check_report = compliance_sanitizer.detect_banned_words(raw_subtitles)
    assert check_report["has_banned_words"] is True
    assert check_report["total_matches"] >= 6
    matched_words = [m["original_word"] for m in check_report["matches"]]
    assert "驾照" in matched_words
    assert "钱" in matched_words
    assert "体检" in matched_words
    assert "最快" in matched_words
    assert "便宜" in matched_words
    assert "关注" in matched_words
    assert "评论区" in matched_words

    # 2. 字幕脱敏清洗
    sanitized_subs = compliance_sanitizer.sanitize_subtitles(raw_subtitles)
    assert sanitized_subs[0]["corrected_text"] == "在杭州考一个贺照要多少銭"
    assert sanitized_subs[1]["corrected_text"] == "首先呢就是四科考试弗和体脸弗"
    assert "蕞快" in sanitized_subs[2]["corrected_text"]
    assert "便冝" in sanitized_subs[2]["corrected_text"]
    assert "关主" in sanitized_subs[3]["corrected_text"]
    assert "平沦区" in sanitized_subs[3]["corrected_text"]

    # 3. 验证高亮词无损传递
    hw0 = sanitized_subs[0]["highlight_words"]
    assert hw0[0]["word"] == "杭州"
    assert hw0[1]["word"] == "多少銭"

    hw1 = sanitized_subs[1]["highlight_words"]
    assert hw1[0]["word"] == "四科考试弗"
    assert hw1[1]["word"] == "体脸弗"

    # 4. 生成 ASS 文件并断言样式语法
    ass_path = tmp_path / "test_e2e_compliance.ass"
    generate_ass_file(sanitized_subs, ass_path, strategy={"subtitle_theme": "cinema_shadow", "subtitle_font_size": 72})
    assert ass_path.exists()
    
    ass_content = ass_path.read_text(encoding="utf-8")
    assert "贺照" in ass_content
    assert "多少銭" in ass_content
    assert "体脸弗" in ass_content
    assert "弗用" not in ass_content # 没出现的词不无中生有
    assert r"{\c&H004444EF&" in ass_content # 高亮标签完整保留

def test_recompose_vs_export_behavior(tmp_path):
    """
    用户核心指示准则：
    - '重新合成' (Recompose/Preview): 绝对不做违禁词处理，保持自然原样可读字幕
    - '视频导出' (Export): 仅在导出时做形似字/拆字清洗
    """
    sample_subs = [
        {
            "start_time": 0.0,
            "end_time": 3.0,
            "raw_text": "在杭州考驾照要多少钱？现在报名最快最便宜！",
            "corrected_text": "在杭州考驾照要多少钱？现在报名最快最便宜！",
            "highlight_words": [
                {"word": "驾照", "color": "#38BDF8", "category": "keyword"},
                {"word": "多少钱", "color": "#EF4444", "category": "price"}
            ]
        }
    ]

    # 1. 重新合成场景 (filter_banned_words=False)
    filter_banned_words_recompose = False
    recompose_subs = [s.copy() for s in sample_subs]
    if filter_banned_words_recompose:
        recompose_subs = compliance_sanitizer.sanitize_subtitles(recompose_subs)

    recompose_ass_path = tmp_path / "test_recompose_subtitles.ass"
    generate_ass_file(recompose_subs, recompose_ass_path, strategy={"subtitle_theme": "cinema_shadow"})
    recompose_ass = recompose_ass_path.read_text(encoding="utf-8")

    # 断言重新合成保留原文，绝不出现形似字
    assert "驾照" in recompose_ass
    assert "多少钱" in recompose_ass
    assert "贺照" not in recompose_ass
    assert "銭" not in recompose_ass
    assert "蕞快" not in recompose_ass

    # 2. 视频导出场景 (filter_banned_words=True)
    filter_banned_words_export = True
    export_subs = [s.copy() for s in sample_subs]
    if filter_banned_words_export:
        export_subs = compliance_sanitizer.sanitize_subtitles(export_subs)

    export_ass_path = tmp_path / "test_export_subtitles.ass"
    generate_ass_file(export_subs, export_ass_path, strategy={"subtitle_theme": "cinema_shadow"})
    export_ass = export_ass_path.read_text(encoding="utf-8")

    # 断言导出成片执行了合规脱敏清洗
    assert "贺照" in export_ass
    assert "多少銭" in export_ass
    assert "蕞快" in export_ass
    assert "便冝" in export_ass
    assert "驾照" not in export_ass
    assert "多少钱" not in export_ass