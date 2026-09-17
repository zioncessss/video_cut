"""高亮词三源合并（词库 ∪ AI ∪ 手动）测试。

遵循 AGENTS.md 测试边界：LLM 输出一律 mock（仅 tests/ 内），embedded 为真实词库引擎；
绝不发起真实网络调用。
"""
import asyncio
import json
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.harness_bridge import llm_client
from app.harness_bridge.api_engine import ApiHarnessBridge
from app.harness_bridge.base import HarnessCorrectionRequest
from app.harness_bridge.embedded import EmbeddedHarnessBridge


def _src(word_list, word):
    """取指定词的来源标记，未命中返回 None"""
    for w in word_list or []:
        if w.get("word") == word:
            return w.get("source")
    return None


def test_embedded_glossary_highlight_words_tagged():
    """embedded 词库引擎：命中的词库关键词必须带 source=glossary 的 highlight_words"""
    req = HarnessCorrectionRequest(
        raw_subtitles=[{"id": "h1", "raw_text": "科目二倒库一把过秘籍", "corrected_text": "科目二倒库一把过秘籍"}]
    )
    res = asyncio.run(EmbeddedHarnessBridge().correct_subtitles(req))
    seg = res.updated_subtitles[0]
    hw = seg.get("highlight_words") or []
    words = [w.get("word") for w in hw]
    assert "一把过" in words, f"词库强调词应命中: {words}"
    assert _src(hw, "一把过") == "glossary"
    # matched_keywords 兼容字段保留
    assert "一把过" in (seg.get("matched_keywords") or [])


def test_api_ai_highlight_merged_with_glossary_priority(monkeypatch):
    """api 引擎：AI 词标记 source=ai；与词库重复的词以词库（确定性）来源为准"""
    canned = json.dumps(
        {
            "subtitles": [
                # AI 返回 '五万平'（词库已有，来源应归 glossary）与 '价格'（词库外，来源 ai）
                {"id": "h2", "corrected_text": "自建五万平训练场价格透明", "highlight_keywords": ["五万平", "价格"]},
            ],
            "corrections": [],
        },
        ensure_ascii=False,
    )

    async def fake_chat(prompt, timeout=30.0, system=None, model_override=None, provider=None):
        return True, canned, 88.8

    monkeypatch.setattr(llm_client, "chat_completion", fake_chat)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "m", "source": "测试"})

    req = HarnessCorrectionRequest(
        raw_subtitles=[{"id": "h2", "raw_text": "自建五万平训练场价格透明", "corrected_text": "自建五万平训练场价格透明"}]
    )
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(req))
    seg = res.updated_subtitles[0]
    hw = seg.get("highlight_words") or []
    words = [w.get("word") for w in hw]
    assert "五万平" in words and "价格" in words, f"AI 词与词库词都应出现: {words}"
    assert _src(hw, "五万平") == "glossary", "词库命中的词来源必须优先标 glossary"
    assert _src(hw, "价格") == "ai", "词库外的 AI 判定词来源必须标 ai"


def test_build_highlight_words_dedup_and_priority():
    """合并工具函数：长词优先、去重、AI 词不覆盖词库词"""
    from app.native_engine.keyword_matcher import build_highlight_words

    merged = build_highlight_words("从今年九月份开始湖州驾校", ai_keywords=["九月份", "湖州驾校", "九月份"])
    words = [w["word"] for w in merged]
    assert words.count("九月份") == 1, "重复 AI 词必须去重"
    assert _src(merged, "湖州驾校") == "glossary"
    assert _src(merged, "九月份") == "ai"
