import pytest
import json
from pathlib import Path
from app.core.compliance_sanitizer import ComplianceSanitizer

def test_sanitizer_reloads_and_has_all_26_mappings(tmp_path):
    config_file = tmp_path / "banned_words.json"
    sanitizer = ComplianceSanitizer(config_path=config_file)
    mappings = sanitizer.get_mappings()
    
    expected_keys = [
        "新政策", "快至35天", "驾驶证", "身份证", "评论区", "绿泡泡",
        "最低", "最快", "特惠", "优惠", "价格", "很快", "便宜", "私信",
        "学费", "驾照", "关注", "改革", "绝对", "体检", "费用", "评论",
        "最", "钱", "骗", "费"
    ]
    for k in expected_keys:
        assert k in mappings, f"Missing mapping for {k}"
    
    assert mappings["驾照"] == "贺照"
    assert mappings["钱"] == "銭"
    assert mappings["学费"] == "学弗"
    assert mappings["体检"] == "体脸"
    assert mappings["骗"] == "马扁"

def test_longest_match_first_priority(tmp_path):
    config_file = tmp_path / "banned_words.json"
    sanitizer = ComplianceSanitizer(config_path=config_file)
    
    # "最快" vs "最": 必须优先替换 "最快" -> "蕞快"，而不是先被 "最" 替换为 "蕞快"
    text1 = "我们的出证速度是最快的"
    res1 = sanitizer.sanitize_text(text1)
    assert "蕞快" in res1
    assert "蕞快的" in res1
    
    # "最低" vs "最":
    text2 = "提供全网最低价格"
    res2 = sanitizer.sanitize_text(text2)
    assert "蕞低阶格" in res2

    # "费用" vs "费":
    text3 = "请交纳全部费用"
    res3 = sanitizer.sanitize_text(text3)
    assert "全部弗用" in res3
    assert "全部弗" not in res3.replace("全部弗用", "")

def test_subtitles_and_highlight_words_synchronization(tmp_path):
    config_file = tmp_path / "banned_words.json"
    sanitizer = ComplianceSanitizer(config_path=config_file)

    subtitles = [
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
            "end_time": 4.0,
            "raw_text": "四科考试费三百六",
            "corrected_text": "四科考试费三百六",
            "highlight_words": [
                {"word": "四科考试费", "color": "#EF4444", "category": "price"}
            ]
        }
    ]

    sanitized = sanitizer.sanitize_subtitles(subtitles)
    
    # 验证字幕正文
    assert sanitized[0]["corrected_text"] == "在杭州考一个贺照要多少銭"
    assert sanitized[1]["corrected_text"] == "四科考试弗三百六"

    # 验证高亮词字典同步转换
    hw0 = sanitized[0]["highlight_words"]
    assert hw0[0]["word"] == "杭州"
    assert hw0[1]["word"] == "多少銭"
    assert hw0[1]["color"] == "#EF4444"

    hw1 = sanitized[1]["highlight_words"]
    assert hw1[0]["word"] == "四科考试弗"
    assert hw1[0]["color"] == "#EF4444"

def test_detect_banned_words(tmp_path):
    config_file = tmp_path / "banned_words.json"
    sanitizer = ComplianceSanitizer(config_path=config_file)

    subtitles = [
        {"corrected_text": "湖州驾校大改革：学车一口价"},
        {"corrected_text": "没有隐形收费与模拟费"},
        {"corrected_text": "点个红心加关注，评论区找我聊"}
    ]

    report = sanitizer.detect_banned_words(subtitles)
    assert report["has_banned_words"] is True
    assert report["total_matches"] >= 4
    
    matched_words = [m["original_word"] for m in report["matches"]]
    assert "改革" in matched_words
    assert "费" in matched_words
    assert "关注" in matched_words
    assert "评论区" in matched_words

def test_mtime_hot_reload(tmp_path):
    import time
    config_file = tmp_path / "banned_words.json"
    sanitizer = ComplianceSanitizer(config_path=config_file)
    
    # 原本驾照是贺照
    assert sanitizer.sanitize_text("学驾照") == "学贺照"
    
    # 模拟外部编辑 JSON
    time.sleep(0.05)
    new_data = {
        "mappings": {
            "驾照": "车召",
            "钱": "米"
        }
    }
    config_file.write_text(json.dumps(new_data, ensure_ascii=False), encoding="utf-8")
    
    # 热更新生效
    assert sanitizer.sanitize_text("学驾照要多少钱") == "学车召要多少米"