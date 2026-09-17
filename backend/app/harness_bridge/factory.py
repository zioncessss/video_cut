from typing import Dict
from app.core import config
from app.harness_bridge.base import BaseHarnessBridge
from app.harness_bridge.embedded import EmbeddedHarnessBridge
from app.harness_bridge.codex import CodexHarnessBridge
from app.harness_bridge.zcode import ZCodeHarnessBridge
from app.harness_bridge.api_engine import ApiHarnessBridge

_instances: Dict[str, BaseHarnessBridge] = {}

def get_harness_by_key(key: str) -> BaseHarnessBridge:
    k = key.lower()
    if k == "zcode":
        if "zcode" not in _instances:
            _instances["zcode"] = ZCodeHarnessBridge()
        return _instances["zcode"]
    elif k == "codex":
        if "codex" not in _instances:
            _instances["codex"] = CodexHarnessBridge()
        return _instances["codex"]
    elif k == "api":
        if "api" not in _instances:
            _instances["api"] = ApiHarnessBridge()
        return _instances["api"]
    else:
        if "embedded" not in _instances:
            _instances["embedded"] = EmbeddedHarnessBridge()
        return _instances["embedded"]

def get_active_harness() -> BaseHarnessBridge:
    """
    Tier A（固定格式任务：字幕纠偏等）桥接器：由设置页 active_harness 决定。
    支持 'api'（直连大模型API）、'codex'、'zcode'、'embedded'。
    """
    return get_harness_by_key(config.ACTIVE_HARNESS)

def get_tier_b_harness() -> BaseHarnessBridge:
    """
    Tier B（开放式任务：自由指令理解、剪辅聊天）桥接器：
    与 active_harness 解耦，按本机可用性自动选择 codex > zcode > embedded。
    注意：embedded 仅具备词库确定性纠偏能力，落到它时开放式任务会显式报错（诚实提示，不返回预置话术）。
    """
    if config.has_codex_available():
        return get_harness_by_key("codex")
    if config.has_zcode_available():
        return get_harness_by_key("zcode")
    return get_harness_by_key("embedded")
