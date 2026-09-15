from typing import Dict
from app.core import config
from app.harness_bridge.base import BaseHarnessBridge
from app.harness_bridge.embedded import EmbeddedHarnessBridge
from app.harness_bridge.codex import CodexHarnessBridge
from app.harness_bridge.zcode import ZCodeHarnessBridge

_instances: Dict[str, BaseHarnessBridge] = {}

def get_active_harness() -> BaseHarnessBridge:
    """
    根据当前配置与环境可用性，动态获取对应的 Harness 桥接器单例。
    支持 'zcode', 'codex', 'embedded'。
    """
    key = config.ACTIVE_HARNESS.lower()
    
    if key == "zcode":
        if "zcode" not in _instances:
            _instances["zcode"] = ZCodeHarnessBridge()
        return _instances["zcode"]
    elif key == "codex":
        if "codex" not in _instances:
            _instances["codex"] = CodexHarnessBridge()
        return _instances["codex"]
    else:
        if "embedded" not in _instances:
            _instances["embedded"] = EmbeddedHarnessBridge()
        return _instances["embedded"]
