import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.harness_bridge.zcode import ZCodeHarnessBridge
from app.harness_bridge.factory import get_active_harness
from app.harness_bridge.base import HarnessCorrectionRequest, HarnessInstructionRequest
from app.core import config

def test_zcode_detection():
    bridge = ZCodeHarnessBridge()
    # 只要系统存在 Node 和安装目录的 zcode.cjs 即为 True
    available = config.has_zcode_available()
    assert config.ZCODE_CLI_PATH.exists() == available

def test_zcode_json_extractor():
    bridge = ZCodeHarnessBridge()
    
    # 测试纯 JSON
    t1 = '[{"index": 0, "corrected_text": "科目二倒库"}]'
    assert bridge._extract_json(t1) == [{"index": 0, "corrected_text": "科目二倒库"}]

    # 测试 Markdown 格式包覆
    t2 = '```json\n{"explanation": "已修改", "updates": []}\n```'
    assert bridge._extract_json(t2) == {"explanation": "已修改", "updates": []}

    # 测试混有前后闲聊文本的 JSON
    t3 = '好的，这是修改方案：\n[{"index": 1, "corrected_text": "坡道起步"}]\n希望对你有帮助！'
    assert bridge._extract_json(t3) == [{"index": 1, "corrected_text": "坡道起步"}]

@pytest.mark.asyncio
async def test_zcode_fallback_protection():
    # 传入不存在的 cli 路径，测试是否能平滑兜底而不崩溃
    fake_bridge = ZCodeHarnessBridge(cli_path=Path("D:/not_exist/zcode.cjs"))
    assert await fake_bridge.is_available() is False

    req = HarnessCorrectionRequest(raw_subtitles=[
        {"start_time": 0.0, "end_time": 2.0, "raw_text": "练科尔到库"}
    ])
    res = await fake_bridge.correct_subtitles(req)
    assert len(res) == 1
    # 降级走 embedded 规则
    assert "科目二" in res[0]["corrected_text"] or "倒库" in res[0]["corrected_text"]

@pytest.mark.asyncio
async def test_harness_factory_routing():
    config.ACTIVE_HARNESS = "embedded"
    h1 = get_active_harness()
    assert h1.__class__.__name__ == "EmbeddedHarnessBridge"

    config.ACTIVE_HARNESS = "zcode"
    h2 = get_active_harness()
    assert h2.__class__.__name__ == "ZCodeHarnessBridge"

@pytest.mark.asyncio
async def test_zcode_correct_subtitles_contract(monkeypatch):
    """契约回归：zcode 主路径必须返回 HarnessCorrectionResponse（此前返回裸 List，激活即崩），
    提示词由词库工厂注入，返回结果经词库确定性兜底补纠。"""
    import json as _json
    from app.harness_bridge.base import HarnessCorrectionResponse

    bridge = ZCodeHarnessBridge()
    if not await bridge.is_available():
        pytest.skip("本机无 Node/ZCode CLI，zcode 主路径不适用")

    canned = _json.dumps(
        {
            "subtitles": [
                # 模拟大模型漏纠：'科尔' 未按词库纠为 '科目二'
                {"id": "z1", "corrected_text": "欢迎来到科尔考场教练带你练车", "highlight_keywords": ["考场"]},
            ],
            "corrections": [],
        },
        ensure_ascii=False,
    )

    async def fake_run(prompt, timeout=35):
        assert "纠偏" in prompt, "纠错提示词必须来自词库驱动的 prompting 工厂"
        return canned

    monkeypatch.setattr(bridge, "_run_zcode_prompt", fake_run)

    req = HarnessCorrectionRequest(
        raw_subtitles=[{"id": "z1", "raw_text": "欢迎来到科尔考场教练带你练车", "corrected_text": "欢迎来到科尔考场教练带你练车"}]
    )
    res = await bridge.correct_subtitles(req)
    assert isinstance(res, HarnessCorrectionResponse)
    assert res.harness_engine_used == "zcode"
    # 模型漏纠的 '科尔' 必须被词库兜底补纠为 '科目二'
    assert res.updated_subtitles[0]["corrected_text"] == "欢迎来到科目二考场教练带你练车"

@pytest.mark.asyncio
async def test_zcode_fallback_returns_contract():
    """CLI 不可用降级 embedded 时，同样必须返回契约对象并完成词库纠偏"""
    from app.harness_bridge.base import HarnessCorrectionResponse

    fake_bridge = ZCodeHarnessBridge(cli_path=Path("D:/not_exist/zcode.cjs"))
    assert await fake_bridge.is_available() is False

    req = HarnessCorrectionRequest(raw_subtitles=[{"id": "a", "raw_text": "福州价效迎来大改革"}])
    res = await fake_bridge.correct_subtitles(req)
    assert isinstance(res, HarnessCorrectionResponse)
    assert "fallback" in res.harness_engine_used
    assert "湖州驾校" in res.updated_subtitles[0]["corrected_text"]
