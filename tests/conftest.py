"""全局测试隔离夹具：
1. 在导入任何 app 模块之前，把 SQLite 重定向到临时库，测试绝不读写真实 storage/videocut.db。
2. 自动快照/恢复 config 全局状态，防止单个测试改写 ACTIVE_HARNESS 等全局配置泄漏到其它测试。
"""
import os
import tempfile

import pytest

_TEST_DB = os.path.join(tempfile.gettempdir(), "videocut_pytest_common.db")
os.environ["VIDEOCUT_DB_PATH"] = _TEST_DB

_TEST_STORAGE = os.path.join(tempfile.gettempdir(), "videocut_pytest_storage")
os.environ["VIDEOCUT_STORAGE_DIR"] = _TEST_STORAGE

# 确保隔离存储目录存在，并复制词库配置文件供测试只读使用（防止缺失告警与断言失败）
os.makedirs(_TEST_STORAGE, exist_ok=True)
_real_glossary = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "glossary.json")
if os.path.exists(_real_glossary):
    import shutil
    shutil.copyfile(_real_glossary, os.path.join(_TEST_STORAGE, "glossary.json"))

# 每个测试会话从干净库和存储目录开始，杜绝跨会话脏数据与真实目录污染
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


@pytest.fixture(autouse=True)
def _mock_dummy_transcribe_for_fake_test_files(monkeypatch):
    """测试代码隔离（AGENTS.md）：仅针对虚拟测试生成的微型文件（<1KB 且非真实音视频）提供测试桩，真实运行绝不 mock"""
    from app.native_engine.asr_runner import asr_runner
    orig_transcribe = asr_runner.transcribe

    def safe_transcribe(video_path):
        if hasattr(video_path, "exists") and video_path.exists() and video_path.stat().st_size < 1024:
            return [
                {
                    "start_time": 0.0,
                    "end_time": 3.0,
                    "raw_text": "测试第一句字幕",
                    "corrected_text": "测试第一句字幕",
                    "words": [
                        {"word": "测试", "start": 0.0, "end": 1.0},
                        {"word": "第一句", "start": 1.0, "end": 2.0},
                        {"word": "字幕", "start": 2.0, "end": 3.0},
                    ]
                },
                {
                    "start_time": 3.2,
                    "end_time": 6.0,
                    "raw_text": "测试第二句学车场地实况",
                    "corrected_text": "测试第二句学车场地实况",
                    "words": [
                        {"word": "测试", "start": 3.2, "end": 4.0},
                        {"word": "第二句", "start": 4.0, "end": 5.0},
                        {"word": "实况", "start": 5.0, "end": 6.0},
                    ]
                }
            ]
        return orig_transcribe(video_path)

    monkeypatch.setattr(asr_runner, "transcribe", safe_transcribe)


