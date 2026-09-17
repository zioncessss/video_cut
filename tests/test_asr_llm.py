import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.keyword_matcher import match_keywords_in_segment
from app.harness_bridge.embedded import EmbeddedHarnessBridge
from app.harness_bridge.base import HarnessCorrectionRequest

def test_keyword_matcher():
    # 测试场地关键词匹配
    seg1 = {"raw_text": "今天带大家看下我们的五万平标准化训练场", "corrected_text": "今天带大家看下我们的五万平标准化训练场"}
    res1 = match_keywords_in_segment(seg1["corrected_text"])
    assert res1["matched_category"] == "venue"
    assert "训练场" in res1["matched_keywords"] or "五万平" in res1["matched_keywords"]

    # 测试体验（原体检）关键词匹配：005 起 medical 分类更名为 experience
    seg2 = {"raw_text": "报名后可以直接在一站式体检大厅体检", "corrected_text": "报名后可以直接在一站式体检大厅体检"}
    res2 = match_keywords_in_segment(seg2["corrected_text"])
    assert res2["matched_category"] == "experience"
    assert "体检" in res2["matched_keywords"]

    # 测试练车/教练关键词匹配
    seg3 = {"raw_text": "科目二倒车入库其实非常简单", "corrected_text": "科目二倒车入库其实非常简单"}
    res3 = match_keywords_in_segment(seg3["corrected_text"])
    assert res3["matched_category"] == "lesson"
    assert "科目二" in res3["matched_keywords"] or "倒库" in res3["matched_keywords"]

@pytest.mark.asyncio
async def test_embedded_harness_correction():
    bridge = EmbeddedHarnessBridge()
    assert await bridge.is_available() is True

    raw_subs = [
        {"id": "s1", "start_time": 0.0, "end_time": 3.0, "raw_text": "科二到库技巧", "corrected_text": "科二到库技巧"},
        {"id": "s2", "start_time": 3.0, "end_time": 6.0, "raw_text": "体检只要十分钟", "corrected_text": "体检只要十分钟"}
    ]
    req = HarnessCorrectionRequest(raw_subtitles=raw_subs)
    corrected = await bridge.correct_subtitles(req)

    assert len(corrected) == 2
    # 验证驾校高频词纠正
    assert "倒库" in corrected[0]["corrected_text"]
    assert "体检" in corrected[1]["corrected_text"]
