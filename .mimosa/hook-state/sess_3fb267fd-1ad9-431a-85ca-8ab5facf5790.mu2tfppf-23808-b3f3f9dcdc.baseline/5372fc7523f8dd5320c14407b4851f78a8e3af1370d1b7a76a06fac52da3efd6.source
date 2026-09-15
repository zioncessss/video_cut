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
