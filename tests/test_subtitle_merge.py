import pytest
from app.native_engine.asr_runner import asr_runner

def test_merge_consecutive_short_fragments():
    # 模拟实际音频中容易被切碎的连续短词
    raw_fragments = [
        {"start_time": 24.499, "end_time": 25.213, "raw_text": "评论区", "corrected_text": "评论区"},
        {"start_time": 25.213, "end_time": 25.689, "raw_text": "找我", "corrected_text": "找我"},
        {"start_time": 25.689, "end_time": 26.640, "raw_text": "聊一下吧", "corrected_text": "聊一下吧"}
    ]
    merged = asr_runner.merge_short_segments(raw_fragments)
    assert len(merged) == 1
    assert merged[0]["raw_text"] == "评论区找我聊一下吧"
    assert merged[0]["start_time"] == 24.499
    assert merged[0]["end_time"] == 26.640

def test_do_not_merge_across_large_gap():
    # 模拟中间有大于 0.5s 的长停顿/思考
    raw_fragments = [
        {"start_time": 0.0, "end_time": 1.0, "raw_text": "第一步", "corrected_text": "第一步"},
        {"start_time": 2.0, "end_time": 3.0, "raw_text": "第二步", "corrected_text": "第二步"}
    ]
    merged = asr_runner.merge_short_segments(raw_fragments)
    assert len(merged) == 2
    assert merged[0]["raw_text"] == "第一步"
    assert merged[1]["raw_text"] == "第二步"

def test_do_not_merge_across_sentence_terminators():
    # 模拟句末有句号或问号
    raw_fragments = [
        {"start_time": 0.0, "end_time": 1.0, "raw_text": "好了吗？", "corrected_text": "好了吗？"},
        {"start_time": 1.1, "end_time": 2.0, "raw_text": "出发", "corrected_text": "出发"}
    ]
    merged = asr_runner.merge_short_segments(raw_fragments)
    assert len(merged) == 2

def test_do_not_exceed_max_chars():
    # 模拟合并后会超过 max_chars (14 字)
    raw_fragments = [
        {"start_time": 0.0, "end_time": 2.0, "raw_text": "我们现在学车通通一口价", "corrected_text": "我们现在学车通通一口价"}, # 11字
        {"start_time": 2.1, "end_time": 3.5, "raw_text": "不收燃油费", "corrected_text": "不收燃油费"} # 5字，合计16字 > 14字
    ]
    merged = asr_runner.merge_short_segments(raw_fragments, max_chars=14)
    assert len(merged) == 2
