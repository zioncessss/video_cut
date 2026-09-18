import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import httpx

from app.main import app
from app.core import config

client = TestClient(app)

def test_settings_get_contains_asr_provider_and_masks_key(monkeypatch, tmp_path):
    """验证 GET /settings 返回 asr_provider 且绝不泄漏明文 Key"""
    fake_key = "sk-api-secret1234567890abcdef"
    monkeypatch.setattr(config, "LLM_API_KEY", fake_key)
    monkeypatch.setattr(config, "ASR_PROVIDER", "minimax")
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")

    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    data = res.json()

    assert data["asr_provider"] == "minimax"
    assert data["llm_api_key"] == ""
    assert data["llm_api_key_configured"] is True
    assert data["llm_api_key_masked"] == "sk-a****cdef"
    assert fake_key not in json.dumps(data), "明文 Key 严禁出现在 API 响应中"

    # engine_config.api 应包含 asr_provider
    assert data["engine_config"]["api"]["asr_provider"] == "minimax"

def test_settings_put_and_post_updates_asr_provider(monkeypatch, tmp_path):
    """验证 PUT 与 POST /settings 均支持更新 asr_provider"""
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")

    # 测试 POST 更新
    payload = {
        "active_harness": "api",
        "llm_model": "MiniMax-Text-01",
        "llm_protocol": "openai",
        "asr_provider": "local"
    }
    res = client.post("/api/v1/settings", json=payload)
    assert res.status_code == 200
    assert config.ASR_PROVIDER == "local"

    # 测试 PUT 更新
    payload["asr_provider"] = "minimax"
    res = client.put("/api/v1/settings", json=payload)
    assert res.status_code == 200
    assert config.ASR_PROVIDER == "minimax"

def test_test_connection_success(monkeypatch):
    """验证 POST /settings/test-connection 双通道正常探测成功"""
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-test-key")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.minimaxi.com/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "MiniMax-Text-01")

    mock_llm_resp = MagicMock()
    mock_llm_resp.status_code = 200
    mock_llm_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "pong"}}]
    }

    mock_stt_resp = MagicMock()
    mock_stt_resp.status_code = 200
    mock_stt_resp.json.return_value = {
        "text": "",
        "segments": []
    }

    async def fake_post(url, *args, **kwargs):
        if "chat/completions" in url:
            return mock_llm_resp
        return mock_stt_resp

    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        res = client.post("/api/v1/settings/test-connection", json={
            "api_key": "sk-test-key",
            "base_url": "https://api.minimaxi.com/v1",
            "model": "MiniMax-Text-01"
        })
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 0
        assert body["data"]["llm_status"] == "ok"
        assert body["data"]["asr_status"] == "ok"
        assert body["data"]["model_used"] == "MiniMax-Text-01"
        assert body["data"]["llm_latency_ms"] >= 0
        assert body["data"]["asr_latency_ms"] >= 0

def test_test_connection_missing_key(monkeypatch):
    """未配置或未提供 Key 时应报错"""
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(config, "MINIMAX_API_KEY", "")

    res = client.post("/api/v1/settings/test-connection", json={})
    assert res.status_code in (400, 500)
    body = res.json()
    assert "Key" in body.get("detail", "") or "key" in body.get("detail", "").lower()

def test_test_connection_auth_failure(monkeypatch):
    """MiniMax 鉴权 401 失败时应返回明确错误"""
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-invalid-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized: invalid api key"

    async def fake_post(url, *args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        res = client.post("/api/v1/settings/test-connection", json={
            "api_key": "sk-invalid-key"
        })
        assert res.status_code == 500
        assert "401" in res.json().get("detail", "")
