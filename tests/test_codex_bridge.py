import pytest
import asyncio
import json
from app.harness_bridge.codex import CodexHarnessBridge
from app.harness_bridge.base import HarnessCorrectionRequest, HarnessInstructionRequest

@pytest.fixture
def codex_bridge():
    return CodexHarnessBridge()

def test_codex_extract_json(codex_bridge):
    # 1. 直接 JSON
    assert codex_bridge._extract_json('{"key": "value"}') == {"key": "value"}
    # 2. Markdown 块
    assert codex_bridge._extract_json('Here is output:\n```json\n{"status": "ok", "num": 10}\n```') == {"status": "ok", "num": 10}
    # 3. 带前后字符的花括号
    assert codex_bridge._extract_json('Thought process... {"res": [1, 2, 3]} End.') == {"res": [1, 2, 3]}

@pytest.mark.asyncio
async def test_codex_is_available(codex_bridge):
    avail = await codex_bridge.is_available()
    assert isinstance(avail, bool)

@pytest.mark.asyncio
async def test_codex_ping_probe(codex_bridge):
    if not await codex_bridge.is_available():
        pytest.skip("Codex CLI not installed in PATH")
    
    success, model_name, latency, msg = await codex_bridge.ping()
    # 验证探针返回合规结构与延迟
    assert isinstance(success, bool)
    assert latency >= 0.0
    if success:
        assert "连通正常" in msg or "ok" in msg.lower()

@pytest.mark.asyncio
async def test_codex_correct_subtitles(codex_bridge, monkeypatch):
    """
    确定性验证 codex 纠错链路（mock 只存在于 tests/，不在生产链路注入假数据）：
    1. 纠错提示词必须由词库 glossary.json 动态注入背景知识；
    2. 模拟模型漏纠（返回文本仍含'科尔'），词库确定性兜底必须补纠为'科目二'。
    若本机未安装 codex CLI，则走 embedded 降级路径，词库同样保证纠偏结果。
    """
    canned_output = json.dumps(
        {
            "subtitles": [
                {
                    "id": "sub-1",
                    # 模拟大模型漏纠：仍保留 '科尔' 未按词库纠为 '科目二'
                    "corrected_text": "欢迎来到科尔考场教练带你练车",
                    "highlight_keywords": ["科尔考场"],
                }
            ],
            "corrections": [],
        },
        ensure_ascii=False,
    )

    async def fake_run_codex_cli(prompt, timeout=60.0, model_override=None):
        assert "湖州驾校" in prompt, "纠错提示词必须包含词库注入的背景知识"
        return True, canned_output, 12.3

    monkeypatch.setattr(codex_bridge, "_run_codex_cli", fake_run_codex_cli)

    req = HarnessCorrectionRequest(
        raw_subtitles=[
            {
                "id": "sub-1",
                "start_time": 0.0,
                "end_time": 3.0,
                "raw_text": "欢迎来到科尔考场教练带你练车",
                "corrected_text": "欢迎来到科尔考场教练带你练车"
            }
        ]
    )
    res = await codex_bridge.correct_subtitles(req)
    assert res.updated_subtitles is not None
    assert len(res.updated_subtitles) == 1
    # 无论是真实 Codex 执行还是降级，词库兜底都必须将“科尔”纠偏为“科目二”
    corrected_text = res.updated_subtitles[0].get("corrected_text", "")
    assert "科目二" in corrected_text
    assert "科尔" not in corrected_text
    assert "codex" in res.harness_engine_used

@pytest.mark.asyncio
async def test_codex_natural_instruction(codex_bridge):
    req = HarnessInstructionRequest(
        current_project_state={
            "subtitles": [
                {"id": "s1", "start_time": 0.0, "end_time": 2.5, "corrected_text": "普通开场"}
            ],
            "broll_replacements": []
        },
        user_instruction="把第1句文案润色为热情的迎新词",
        available_materials=[]
    )
    res = await codex_bridge.apply_natural_instruction(req)
    assert res.explanation != ""
    assert res.updated_subtitles is not None
    assert "codex" in res.harness_engine_used
