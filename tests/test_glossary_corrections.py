"""
词库驱动纠偏链路测试：验证 storage/glossary.json 是唯一映射源，
且长词优先、幂等、受保护词不被波及（测试数据仅存在于 tests/ 中，不注入生产链路）。
"""
import asyncio

from app.core.config import (
    apply_glossary_corrections,
    get_asr_initial_prompt,
    get_common_corrections,
    load_glossary,
)
from app.harness_bridge.embedded import EmbeddedHarnessBridge


def test_load_glossary_reads_real_file():
    """修复点回归：load_glossary 必须真实读取 glossary.json，而非静默回退默认值"""
    glossary = load_glossary()
    corrections = glossary.get("common_corrections") or {}
    assert corrections, "glossary.json 存在且含 common_corrections 时必须真实加载"
    assert corrections.get("福州") == "湖州"


def test_corrections_sorted_longest_first():
    """长词必须排在最前，防止'福州驾校'被'福州'规则截断替换"""
    corrections = get_common_corrections()
    keys = list(corrections.keys())
    assert keys == sorted(keys, key=len, reverse=True)


def test_apply_glossary_idempotent():
    once, changes_once = apply_glossary_corrections("从今年九月份开始福州价效迎来大改革")
    assert "湖州驾校" in once
    assert "福州" not in once and "价效" not in once
    twice, changes_twice = apply_glossary_corrections(once)
    assert twice == once
    assert changes_twice == []
    assert all(c["from"] and c["to"] for c in changes_once)


def test_apply_glossary_keeps_clean_text_untouched():
    text, changes = apply_glossary_corrections("专业金牌教练手把手教学")
    assert text == "专业金牌教练手把手教学"
    assert changes == []


def test_embedded_bridge_driven_by_glossary():
    """嵌入式纠错引擎必须走词库映射，而不是任何硬编码词表"""
    bridge = EmbeddedHarnessBridge()
    request_payload = {
        "raw_subtitles": [
            {"id": "s1", "raw_text": "福州价效迎来大改革", "corrected_text": "福州价效迎来大改革"},
            {"id": "s2", "raw_text": "老师说刻一很容易挂", "corrected_text": "老师说刻一很容易挂"},
            {"id": "s3", "raw_text": "评论区找我聊一下吧", "corrected_text": "评论区找我聊一下吧"},
        ]
    }
    from app.harness_bridge.base import HarnessCorrectionRequest
    res = asyncio.run(bridge.correct_subtitles(HarnessCorrectionRequest(**request_payload)))
    by_id = {s["id"]: s for s in res.updated_subtitles}
    assert by_id["s1"]["corrected_text"] == "湖州驾校迎来大改革"
    assert by_id["s2"]["corrected_text"] == "老师说科一很容易挂"
    # 无错字句子原样保留
    assert by_id["s3"]["corrected_text"] == "评论区找我聊一下吧"
    assert res.harness_engine_used == "embedded"


def test_asr_initial_prompt_from_glossary():
    """ASR initial_prompt 必须由词库生成并包含正确专名词"""
    prompt = get_asr_initial_prompt()
    assert prompt
    assert "湖州" in prompt
