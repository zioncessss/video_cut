"""全局测试隔离夹具：
1. 在导入任何 app 模块之前，把 SQLite 重定向到临时库，测试绝不读写真实 storage/videocut.db。
2. 自动快照/恢复 config 全局状态，防止单个测试改写 ACTIVE_HARNESS 等全局配置泄漏到其它测试。
"""
import os
import tempfile

import pytest

_TEST_DB = os.path.join(tempfile.gettempdir(), "videocut_pytest_common.db")
os.environ["VIDEOCUT_DB_PATH"] = _TEST_DB

# 每个测试会话从干净库开始，杜绝跨会话脏数据
for suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TEST_DB + suffix)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _isolate_config_globals():
    """每个测试前快照 config 全局配置，测试后恢复，杜绝测试间状态泄漏"""
    from app.core import config as app_config

    snapshot = {
        "ACTIVE_HARNESS": app_config.ACTIVE_HARNESS,
        "LLM_API_KEY": app_config.LLM_API_KEY,
        "LLM_BASE_URL": app_config.LLM_BASE_URL,
        "LLM_MODEL": app_config.LLM_MODEL,
        "LLM_PROTOCOL": app_config.LLM_PROTOCOL,
    }
    yield
    for key, value in snapshot.items():
        setattr(app_config, key, value)

