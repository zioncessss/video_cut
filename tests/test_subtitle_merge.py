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


def test_split_long_clause_natural_semantics():
    """验证长口播子句不会按 10 字硬编码切断中文词语（如'没有'、'我们在安吉'）"""
    long_clause = [{
        "id": "clause_1",
        "start_time": 3.0,
        "end_time": 12.0,
        "raw_text": "在湖州学个驾校真的没有你们想的弄复杂像我们在安吉这边呢大家如果想学车",
        "corrected_text": "在湖州学个驾校真的没有你们想的弄复杂像我们在安吉这边呢大家如果想学车"
    }]
    split_res = asr_runner.split_into_readable_segments(long_clause, max_chars=14)
    assert len(split_res) >= 2
    
    # 验证关键词汇绝不跨句被切裂
    full_texts = [s["raw_text"] for s in split_res]
    for text in full_texts:
        assert not text.endswith("没"), "词语'没有'被生硬切断：前句结尾不应为'没'"
        assert not text.startswith("有你们"), "词语'没有'被生硬切断：后句开头不应为'有你们'"
        assert not text.endswith("像我"), "词语'像我们'被切断：前句结尾不应为'像我'"
        assert not text.startswith("们在"), "词语'我们在'被切断：后句开头不应为'们在'"
        assert len(text) <= 14, f"子句字数不得超过 14 字: {text}"


def test_split_with_word_timestamps_preserves_acoustic_timing():
    """验证当存在物理词时间戳时，切分后严格沿用首词 start 与尾词 end，而非字数线性估算"""
    words = [
        {"word": "在湖州", "start": 3.1, "end": 3.7},
        {"word": "学个驾校", "start": 3.7, "end": 4.8},
        {"word": "真的没有", "start": 5.2, "end": 6.0},
        {"word": "你们想的那么复杂", "start": 6.0, "end": 7.9},
    ]
    clause = [{
        "id": "clause_2",
        "start_time": 3.1,
        "end_time": 7.9,
        "raw_text": "在湖州学个驾校真的没有你们想的那么复杂",
        "corrected_text": "在湖州学个驾校真的没有你们想的那么复杂",
        "words": words
    }]
    split_res = asr_runner.split_into_readable_segments(clause, max_chars=12)
    assert len(split_res) == 2
    # 第一段应是 '在湖州学个驾校'，时间严格取真实词物理时间戳 3.1 ~ 4.8
    assert split_res[0]["start_time"] == 3.1
    assert split_res[0]["end_time"] == 4.8
    # 第二段应是 '真的没有你们想的那么复杂'，时间严格取 5.2 ~ 7.9
    assert split_res[1]["start_time"] == 5.2
    assert split_res[1]["end_time"] == 7.9


def test_anti_orphan_no_single_char_tail():
    """验证防孤字/防碎尾保护：19字完整句（如'模拟费'）绝不拆出单字'费'孤儿卡片"""
    clause_text = "还有一个就是大家通常不知道的就是模拟费"
    words = [{"word": ch, "start": 22.5 + i * 0.2, "end": 22.5 + (i + 1) * 0.2} for i, ch in enumerate(clause_text)]
    clause = [{
        "id": "clause_sim_fee",
        "start_time": 22.5,
        "end_time": 22.5 + len(clause_text) * 0.2,
        "raw_text": clause_text,
        "corrected_text": clause_text,
        "words": words
    }]
    split_res = asr_runner.split_into_readable_segments(clause, max_chars=18)
    # 19 字处于 soft_max 弹性范围内，严禁拆成 18 + 1 孤字
    assert len(split_res) == 1
    assert split_res[0]["raw_text"] == clause_text
    assert not any(len(s["raw_text"]) == 1 and s["raw_text"] == "费" for s in split_res)


def test_filler_placeholder_filtering():
    """验证独立语气助词/无意义口癖占位符（'呃'、'额'等）被彻底过滤，严防成为独立字幕"""
    segments = [
        {"start_time": 22.3, "end_time": 22.52, "raw_text": "呃", "corrected_text": "呃"},
        {"start_time": 22.54, "end_time": 26.64, "raw_text": "还有一个就是大家通常不知道的就是模拟费", "corrected_text": "还有一个就是大家通常不知道的就是模拟费"},
        {"start_time": 42.84, "end_time": 43.06, "raw_text": "呃", "corrected_text": "呃"},
        {"start_time": 43.08, "end_time": 44.26, "raw_text": "可以滴滴我一下", "corrected_text": "可以滴滴我一下"},
    ]
    cleaned = asr_runner.filter_filler_segments(segments)
    assert len(cleaned) == 2
    assert cleaned[0]["raw_text"] == "还有一个就是大家通常不知道的就是模拟费"
    assert cleaned[1]["raw_text"] == "可以滴滴我一下"
    assert not any(s["raw_text"] == "呃" for s in cleaned)


def test_global_merge_across_short_clauses():
    """验证全局平滑合并：跨句微短碎片（如'还有一个就是保险费' + '面签费'）被智能吸收"""
    segments = [
        {"start_time": 11.50, "end_time": 13.16, "raw_text": "还有一个就是保险费", "corrected_text": "还有一个就是保险费"},
        {"start_time": 13.26, "end_time": 13.86, "raw_text": "面签费", "corrected_text": "面签费"},
        {"start_time": 13.86, "end_time": 15.56, "raw_text": "体检费这些加起来大概是一百", "corrected_text": "体检费这些加起来大概是一百"}
    ]
    merged = asr_runner.merge_short_segments(segments, min_chars=4, min_duration=1.0, max_chars=20, max_gap=0.6)
    # 0.6s / 3字 的'面签费'应当吸附进前句'还有一个就是保险费'
    assert len(merged) == 2
    assert "还有一个就是保险费面签费" in merged[0]["raw_text"]

