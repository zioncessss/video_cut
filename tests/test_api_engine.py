"""直连大模型 API 引擎（Tier A）与工厂分层路由测试。

mock 仅存在于 tests/：通过 monkeypatch llm_client 的传输层与提供方解析，
验证 api 引擎的契约、词库兜底与诚实降级标注，不发起真实网络请求。
"""
import asyncio
import json

import pytest
from app.core import config
from app.harness_bridge import llm_client
from app.harness_bridge.api_engine import ApiHarnessBridge
from app.harness_bridge.base import HarnessCorrectionRequest, HarnessCorrectionResponse
from app.harness_bridge.factory import get_harness_by_key, get_tier_b_harness

CANNED_LLM_OUTPUT = json.dumps(
    {
        "subtitles": [
            # 模拟大模型漏纠：'科尔' 未按词库纠为 '科目二'
            {"id": "a1", "corrected_text": "欢迎来到科尔考场教练带你练车", "highlight_keywords": ["考场"]},
        ],
        "corrections": [],
    },
    ensure_ascii=False,
)


def _make_request() -> HarnessCorrectionRequest:
    return HarnessCorrectionRequest(
        raw_subtitles=[{"id": "a1", "raw_text": "欢迎来到科尔考场教练带你练车", "corrected_text": "欢迎来到科尔考场教练带你练车"}]
    )


def test_factory_registers_api_and_tier_b_excludes_it():
    from app.harness_bridge.api_engine import ApiHarnessBridge

    assert isinstance(get_harness_by_key("api"), ApiHarnessBridge)
    # Tier B（开放式任务）永远不路由到 api 引擎
    tier_b = get_tier_b_harness()
    assert not isinstance(tier_b, ApiHarnessBridge)
    assert tier_b.__class__.__name__ in ("CodexHarnessBridge", "ZCodeHarnessBridge", "EmbeddedHarnessBridge")


def test_api_correct_subtitles_contract_and_glossary_net(monkeypatch):
    async def fake_stream(prompt, timeout=120.0, system=None, model_override=None, provider=None):
        assert "纠偏" in prompt, "提示词必须来自词库工厂"
        return True, CANNED_LLM_OUTPUT, 123.4

    monkeypatch.setattr(llm_client, "chat_completion_stream_full", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "m", "source": "测试"})

    res = asyncio.run(ApiHarnessBridge().correct_subtitles(_make_request()))
    assert isinstance(res, HarnessCorrectionResponse)
    assert res.harness_engine_used == "api"
    # 模型漏纠的 '科尔' 被词库兜底补纠
    assert res.updated_subtitles[0]["corrected_text"] == "欢迎来到科目二考场教练带你练车"


def test_api_correction_chunks_large_batch(monkeypatch):
    """超过 12 句自动分块：13 句应产生 2 次请求且结果全量合并，句子绝不丢失"""
    calls = []
    ids_per_call = [[f"s{i}" for i in range(12)], [f"s{i}" for i in range(12, 13)]]

    async def fake_stream(prompt, timeout=120.0, system=None, model_override=None, provider=None):
        idx = len(calls)
        calls.append(prompt)
        ids = ids_per_call[idx]
        return True, json.dumps(
            {"subtitles": [{"id": i, "corrected_text": f"已纠{i}"} for i in ids], "corrections": []},
            ensure_ascii=False,
        ), 10.0

    monkeypatch.setattr(llm_client, "chat_completion_stream_full", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "m", "source": "测试"})

    raws = [{"id": f"s{i}", "raw_text": f"句子{i}", "corrected_text": f"句子{i}"} for i in range(13)]
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(HarnessCorrectionRequest(raw_subtitles=raws)))
    assert len(calls) == 2, "13 句必须分为 2 块请求"
    assert len(res.updated_subtitles) == 13
    assert all(s["corrected_text"] == f"已纠{s['id']}" for s in res.updated_subtitles)
    assert res.harness_engine_used == "api"


def test_api_correction_partial_chunk_failure_degrades_only_that_chunk(monkeypatch):
    """两块中一块失败：失败块降级词库纠偏，成功块保留 AI 结果，标注 partial fallback"""
    ids_per_call = [[f"s{i}" for i in range(12)], [f"s{i}" for i in range(12, 24)]]
    state = {"calls": 0}

    async def fake_stream(prompt, timeout=120.0, system=None, model_override=None, provider=None):
        idx = state["calls"]
        state["calls"] += 1
        if idx == 0:
            ids = ids_per_call[0]
            return True, json.dumps(
                {"subtitles": [{"id": i, "corrected_text": f"AI已纠{i}"} for i in ids], "corrections": []},
                ensure_ascii=False,
            ), 10.0
        return False, "读取响应超时(120s)，模型未在时限内完成生成 [ReadTimeout]", 120000.0

    monkeypatch.setattr(llm_client, "chat_completion_stream_full", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "m", "source": "测试"})

    raws = [{"id": f"s{i}", "raw_text": "福州价效", "corrected_text": "福州价效"} for i in range(24)]
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(HarnessCorrectionRequest(raw_subtitles=raws)))
    assert len(res.updated_subtitles) == 24, "任何块失败都不得丢句"
    assert "partial fallback embedded" in res.harness_engine_used
    # 第 1 块走 AI 结果，第 2 块降级词库（福州价效→湖州驾校）
    assert res.updated_subtitles[0]["corrected_text"] == "AI已纠s0"
    assert res.updated_subtitles[12]["corrected_text"] == "湖州驾校"


def test_api_fallback_labeled_when_provider_missing(monkeypatch):
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: None)
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(_make_request()))
    assert isinstance(res, HarnessCorrectionResponse)
    assert "fallback embedded" in res.harness_engine_used
    # 降级 embedded 后仍由词库完成确定性纠偏，不静默失败
    assert "科目二" in res.updated_subtitles[0]["corrected_text"]


def test_api_fallback_labeled_when_llm_fails_or_malformed(monkeypatch):
    async def fail_stream(prompt, timeout=120.0, system=None, model_override=None, provider=None):
        return False, "读取响应超时(120s)，模型未在时限内完成生成 [ReadTimeout]", 120000.0

    monkeypatch.setattr(llm_client, "chat_completion_stream_full", fail_stream)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "m", "source": "测试"})
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(_make_request()))
    assert "fallback embedded" in res.harness_engine_used
    assert "超时" in res.harness_engine_used


def test_resolve_api_provider_prefers_settings(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key-from-settings")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setattr(config, "LLM_MODEL", "glm-5.3-flash")
    provider = llm_client.resolve_api_provider()
    assert provider["base_url"] == "https://api.example.com/v1"
    assert provider["source"] == "设置页配置"


def test_parse_models_payload_supports_codex_proxy_shape():
    """codex 本地代理返回 {"models": [{slug, display_name}]}，非 OpenAI 标准 data/id 结构，必须兼容"""
    from app.harness_bridge.llm_client import parse_models_payload

    codex_proxy = {"models": [
        {"slug": "glm-5.3-flash", "display_name": "GLM-5.3-Flash", "description": "x"},
        {"slug": "glm-5.3", "display_name": "GLM-5.3", "description": "y"},
    ]}
    assert parse_models_payload(codex_proxy) == ["glm-5.3", "glm-5.3-flash"]

    openai_std = {"data": [{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}]}
    assert parse_models_payload(openai_std) == ["deepseek-chat", "deepseek-reasoner"]

    assert parse_models_payload(["m1", "m2"]) == ["m1", "m2"]
    assert parse_models_payload({}) == []


def test_parse_stream_line_detects_first_content_token():
    """TTFT 探针的 SSE 行判定：role 帧不算，首个内容 delta 才算"""
    from app.harness_bridge.llm_client import parse_stream_line

    assert not parse_stream_line("event: ping")
    assert not parse_stream_line('data: {"choices":[{"delta":{"role":"assistant"}}]}')
    assert not parse_stream_line("data: [DONE]")
    assert not parse_stream_line("data: 不是json")
    assert parse_stream_line('data: {"choices":[{"delta":{"content":"{"}}]}')
    assert parse_stream_line('data: {"choices":[{"delta":{"reasoning_content":"思考中"}}]}')


def test_ping_reports_ttft(monkeypatch):
    """ping 必须走流式 TTFT 测量，返回值即首 Token 毫秒数"""
    async def fake_ttft(prompt, timeout=20.0, system=None, model_override=None):
        assert "status" in prompt
        return True, 342.7, "glm-5.3-flash"

    monkeypatch.setattr(llm_client, "chat_completion_ttft", fake_ttft)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {"base_url": "http://x/v1", "token": "t", "model": "glm-5.3-flash", "source": "测试"})

    ok, model, latency_ms, msg = asyncio.run(ApiHarnessBridge().ping())
    assert ok and model == "glm-5.3-flash"
    assert latency_ms == 342.7
    assert "首 Token" in msg


def test_embedded_open_ended_tasks_raise_honestly():
    """铁律回归：embedded 无开放式任务能力时必须显式报错，严禁返回预置话术/假装成功"""
    from app.harness_bridge.base import HarnessInstructionRequest
    from app.harness_bridge.embedded import EmbeddedHarnessBridge

    bridge = EmbeddedHarnessBridge()
    req = HarnessInstructionRequest(current_project_state={"subtitles": []}, user_instruction="把第1句润色一下")

    with pytest.raises(RuntimeError, match="不支持开放式指令理解"):
        asyncio.run(bridge.apply_natural_instruction(req))

    async def _consume_chat():
        async for _ in bridge.stream_chat("你好"):
            pass

    with pytest.raises(RuntimeError, match="不支持聊天"):
        asyncio.run(_consume_chat())


def test_embedded_correction_still_works_offline():
    """embedded 瘦身后保留唯一真实能力：词库确定性纠偏（离线兜底）"""
    from app.harness_bridge.embedded import EmbeddedHarnessBridge

    res = asyncio.run(EmbeddedHarnessBridge().correct_subtitles(
        HarnessCorrectionRequest(raw_subtitles=[{"id": "e1", "raw_text": "福州价效迎来大改革"}])
    ))
    assert res.harness_engine_used == "embedded"
    assert res.updated_subtitles[0]["corrected_text"] == "湖州驾校迎来大改革"


def test_codex_provider_reads_local_config_only(monkeypatch):
    """codex 提供方必须只读本地 toml，设置页 API 配置对 codex 引擎不可见"""
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://settings-url.example/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "settings-key-should-be-ignored")
    monkeypatch.setattr(config, "get_codex_provider_config", lambda: {
        "base_url": "http://127.0.0.1:15721/v1", "token": "PROXY_MANAGED", "model": "glm-5.3-flash"
    })
    p = llm_client.codex_provider()
    assert p["base_url"] == "http://127.0.0.1:15721/v1"
    assert p["model"] == "glm-5.3-flash"
    assert p["source"].startswith("codex 本地配置")


def test_chat_completion_explicit_provider_wins(monkeypatch):
    """显式传入 provider 时必须直接使用，不得回退解析设置页配置"""
    captured = {}

    async def fake_via(provider, prompt, timeout=30.0, system=None, model_override=None):
        captured["provider"] = provider
        return True, "ok", 1.0

    def _forbidden():
        raise AssertionError("显式指定 provider 时不得再解析设置项")

    monkeypatch.setattr(llm_client, "_chat_via_provider", fake_via)
    monkeypatch.setattr(llm_client, "resolve_api_provider", _forbidden)
    ok, text, _ = asyncio.run(llm_client.chat_completion(
        "hi", provider={"base_url": "http://codex-local/v1", "token": "t", "model": "m", "source": "x"}
    ))
    assert ok
    assert captured["provider"]["base_url"] == "http://codex-local/v1"


def test_codex_bridge_binds_local_provider(monkeypatch):
    """codex 纠错必须把 provider 绑定为 codex 本地配置，而非设置页 API"""
    from app.harness_bridge.codex import CodexHarnessBridge

    captured = {}

    async def fake_chat(prompt, timeout=60.0, system=None, model_override=None, provider=None):
        captured["provider"] = provider
        return True, json.dumps(
            {"subtitles": [{"id": "c1", "corrected_text": "湖州价效"}], "corrections": []},
            ensure_ascii=False,
        ), 5.0

    monkeypatch.setattr(llm_client, "chat_completion", fake_chat)
    monkeypatch.setattr(llm_client, "codex_provider", lambda: {
        "base_url": "http://127.0.0.1:15721/v1", "token": "t", "model": "glm", "source": "codex 本地配置 (~/.codex/config.toml)"
    })

    res = asyncio.run(CodexHarnessBridge().correct_subtitles(
        HarnessCorrectionRequest(raw_subtitles=[{"id": "c1", "raw_text": "福州价效"}])
    ))
    assert captured["provider"]["source"].startswith("codex 本地配置")
    assert res.harness_engine_used == "codex"
    # 模型漏纠的 '福州价效' 由词库兜底补纠
    assert res.updated_subtitles[0]["corrected_text"] == "湖州驾校"


def test_settings_get_never_returns_full_key(monkeypatch, tmp_path):
    """凭据红线：GET /settings 严禁下发 key 明文，只允许掩码与布尔态（测试 key 动态生成，无凭据字面量）"""
    from fastapi.testclient import TestClient
    from app.main import app

    fake_key = "A" * 16
    monkeypatch.setattr(config, "LLM_API_KEY", fake_key)
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")
    client = TestClient(app)
    body = client.get("/api/v1/settings").json()
    assert body["llm_api_key"] == ""
    assert body["llm_api_key_configured"] is True
    assert body["llm_api_key_masked"] == "AAAA****AAAA"
    assert fake_key not in json.dumps(body)


def test_settings_post_blank_key_preserves_existing(monkeypatch, tmp_path):
    """凭据红线：保存时未输入新 key（字段缺省）必须保留已存储的 key，不得清空"""
    from fastapi.testclient import TestClient
    from app.main import app

    original_key = "orig-" + "x" * 12
    new_key = "new-" + "y" * 12
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(config, "LLM_API_KEY", original_key)
    client = TestClient(app)
    res = client.post("/api/v1/settings", json={
        "active_harness": "api", "llm_model": "glm-5.3-flash",
        "llm_base_url": "https://api.example.com/v1", "llm_protocol": "openai",
    })
    assert res.status_code == 200
    assert config.LLM_API_KEY == original_key
    # 新 key 显式提交时正常更新
    res2 = client.post("/api/v1/settings", json={
        "active_harness": "api", "llm_model": "glm-5.3-flash",
        "llm_base_url": "https://api.example.com/v1", "llm_protocol": "openai",
        "llm_api_key": new_key,
    })
    assert res2.status_code == 200
    assert config.LLM_API_KEY == new_key


def test_list_models_endpoint_returns_ids(monkeypatch):
    """/settings/list-models 必须返回 /models 接口解析出的模型 id 列表（传输层 mock 仅在 tests/）"""
    from fastapi.testclient import TestClient
    from app.main import app

    async def fake_list_models(base_url, token="", timeout=15.0):
        assert base_url == "https://api.example.com/v1"
        return True, ["glm-5.3", "glm-5.3-flash"], "获取成功，共 2 个模型"

    monkeypatch.setattr(llm_client, "list_models", fake_list_models)
    client = TestClient(app)
    res = client.post(
        "/api/v1/settings/list-models",
        json={"llm_base_url": "https://api.example.com/v1", "llm_api_key": "test-key"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    assert body["data"]["models"] == ["glm-5.3", "glm-5.3-flash"]


def test_list_models_endpoint_honest_failure(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    async def fail_list_models(base_url, token="", timeout=15.0):
        return False, [], "GET /models 失败 HTTP 401: unauthorized"

    monkeypatch.setattr(llm_client, "list_models", fail_list_models)
    client = TestClient(app)
    res = client.post(
        "/api/v1/settings/list-models",
        json={"llm_base_url": "https://api.example.com/v1"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 1
    assert "401" in body["message"]
    assert body["data"]["models"] == []


def test_minimax_normalize_base_url():
    """测试 MiniMax 等 API base_url 的自动规范化与 /v1 智能补全"""
    assert llm_client.normalize_base_url("https://api.minimaxi.com") == "https://api.minimaxi.com/v1"
    assert llm_client.normalize_base_url("https://api.minimaxi.com/v1") == "https://api.minimaxi.com/v1"
    assert llm_client.normalize_base_url("https://api.minimaxi.com/v1/chat/completions") == "https://api.minimaxi.com/v1"
    assert llm_client.normalize_base_url("https://api.openai.com") == "https://api.openai.com/v1"
    assert llm_client.normalize_base_url("http://127.0.0.1:15721/v1") == "http://127.0.0.1:15721/v1"


def test_minimax_text_01_correction_and_markdown_unwrap(monkeypatch):
    """测试在 OpenAI 兼容格式下 MiniMax-Text-01 正常被识别与消费，markdown 代码块正确解包"""
    captured = {}

    minimax_markdown_response = (
        "好的，为您进行智能字幕纠偏：\n"
        "```json\n"
        "{\n"
        '  "subtitles": [\n'
        '    {"id": "m1", "corrected_text": "欢迎来到科目二考场教练带你练车", "highlight_keywords": ["考场"]}\n'
        "  ],\n"
        '  "corrections": [\n'
        '    {"subtitle_id": "m1", "original_text": "科二", "corrected_text": "科目二", "reason": "术语规范"}\n'
        "  ]\n"
        "}\n"
        "```\n"
        "纠偏完成！"
    )

    async def fake_stream(prompt, timeout=120.0, system=None, model_override=None, provider=None):
        captured["prompt"] = prompt
        return True, minimax_markdown_response, 450.0

    monkeypatch.setattr(llm_client, "chat_completion_stream_full", fake_stream)
    monkeypatch.setattr(llm_client, "resolve_api_provider", lambda: {
        "base_url": "https://api.minimaxi.com/v1",
        "token": "sk-test-minimax",
        "model": "MiniMax-Text-01",
        "source": "设置页配置"
    })

    req = HarnessCorrectionRequest(
        raw_subtitles=[{"id": "m1", "raw_text": "欢迎来到科二考场教练带你练车", "corrected_text": "欢迎来到科二考场教练带你练车"}]
    )
    res = asyncio.run(ApiHarnessBridge().correct_subtitles(req))

    assert isinstance(res, HarnessCorrectionResponse)
    assert res.harness_engine_used == "api"
    assert res.updated_subtitles[0]["corrected_text"] == "欢迎来到科目二考场教练带你练车"
    assert len(res.corrections_summary) >= 1
    assert res.corrections_summary[0].original_text == "科二"
    assert res.corrections_summary[0].corrected_text == "科目二"

