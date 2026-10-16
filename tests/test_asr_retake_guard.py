import pytest
from app.native_engine.asr_runner import ASRRunner

def test_merge_short_segments_retake_guard():
    runner = ASRRunner()
    
    # 口误重读样本：前句读错说了一半，后句重新完整读
    segs = [
        {
            "start_time": 1.0,
            "end_time": 1.8,
            "raw_text": "顺达...",
            "corrected_text": "顺达",
            "words": [{"word": "顺", "start": 1.0, "end": 1.3}, {"word": "达", "start": 1.3, "end": 1.8}]
        },
        {
            "start_time": 2.1,
            "end_time": 4.5,
            "raw_text": "顺达驾校自建训练场",
            "corrected_text": "顺达驾校自建训练场",
            "words": [
                {"word": "顺", "start": 2.1, "end": 2.3},
                {"word": "达", "start": 2.3, "end": 2.5},
                {"word": "驾", "start": 2.5, "end": 2.8},
                {"word": "校", "start": 2.8, "end": 3.1},
                {"word": "自", "start": 3.1, "end": 3.4},
                {"word": "建", "start": 3.4, "end": 3.7},
                {"word": "训", "start": 3.7, "end": 4.0},
                {"word": "练", "start": 4.0, "end": 4.3},
                {"word": "场", "start": 4.3, "end": 4.5},
            ]
        }
    ]
    
    # 期望：重读阻断守卫介入，禁止将口误前缀与后句粘连为同一句
    res = runner.merge_short_segments(segs)
    assert len(res) == 2, f"口误重读短句不应被过早粘联合并，实际长度: {len(res)}"
    assert "顺达" in res[0]["raw_text"]
    assert "顺达驾校" in res[1]["raw_text"]

def test_merge_short_segments_still_merges_normal_short_phrases():
    runner = ASRRunner()
    
    # 正常连续短句呼吁词，应当正常合并
    segs = [
        {
            "start_time": 1.0,
            "end_time": 1.4,
            "raw_text": "评论区",
            "corrected_text": "评论区",
            "words": [{"word": "评", "start": 1.0, "end": 1.1}, {"word": "论", "start": 1.1, "end": 1.3}, {"word": "区", "start": 1.3, "end": 1.4}]
        },
        {
            "start_time": 1.6,
            "end_time": 2.5,
            "raw_text": "找我聊聊",
            "corrected_text": "找我聊聊",
            "words": [{"word": "找", "start": 1.6, "end": 1.8}, {"word": "我", "start": 1.8, "end": 2.0}, {"word": "聊", "start": 2.0, "end": 2.2}, {"word": "聊", "start": 2.2, "end": 2.5}]
        }
    ]
    
    res = runner.merge_short_segments(segs)
    assert len(res) == 1, "非重读的正常相邻短片段应保持正常合并"
    assert res[0]["raw_text"] == "评论区找我聊聊"
