from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import shutil
import time
from typing import Optional
import httpx
from app.core import config
from app.harness_bridge.llm_client import normalize_base_url

router = APIRouter()

class SettingsPayload(BaseModel):
    active_harness: str  # "api", "embedded", "codex", "zcode"
    llm_model: str = "MiniMax-Text-01"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_protocol: str = "openai"  # openai 兼容 /chat/completions；anthropic/gemini 预留
    asr_provider: Optional[str] = None  # "minimax" | "local"
    minimax_api_key: Optional[str] = None
    minimax_base_url: Optional[str] = None

@router.get("")
async def get_settings():
    config.load_settings()
    has_codex = bool(shutil.which("codex"))
    has_zcode = config.has_zcode_available()
    from app.harness_bridge.llm_client import resolve_api_provider, codex_provider
    has_api = resolve_api_provider() is not None
    codex_local = codex_provider() or {}
    # 凭据红线：key 明文严禁下发前端，仅返回掩码与是否已配置
    key = config.LLM_API_KEY or ""
    key_masked = f"{key[:4]}****{key[-4:]}" if len(key) > 8 else ("****" if key else "")
    return {
        "active_harness": config.ACTIVE_HARNESS,
        "llm_model": config.LLM_MODEL,
        "llm_api_key": "",
        "llm_api_key_masked": key_masked,
        "llm_api_key_configured": bool(key),
        "llm_base_url": config.LLM_BASE_URL,
        "llm_protocol": config.LLM_PROTOCOL,
        "asr_provider": config.ASR_PROVIDER,
        "detected_engines": {
            "api": has_api,
            "embedded": True,
            "codex": has_codex,
            "zcode": has_zcode
        },
        # 各引擎实际生效的配置来源摘要（token 不下发）
        "engine_config": {
            "api": {
                "base_url": config.LLM_BASE_URL,
                "has_key": bool(config.LLM_API_KEY),
                "model": config.LLM_MODEL,
                "asr_provider": config.ASR_PROVIDER
            },
            "codex": {
                "base_url": codex_local.get("base_url", ""),
                "model": codex_local.get("model", ""),
                "has_token": bool(codex_local.get("token")),
                "available": has_codex
            },
            "zcode": {"cli_path": str(config.ZCODE_CLI_PATH) if has_zcode else None, "available": has_zcode},
            "embedded": {"mode": "词库确定性纠偏（无网络依赖）"}
        },
        "zcode_path": str(config.ZCODE_CLI_PATH) if has_zcode else None
    }

@router.post("")
@router.put("")
async def update_settings(payload: SettingsPayload):
    save_data = {
        "active_harness": payload.active_harness,
        "llm_model": payload.llm_model,
        "llm_protocol": payload.llm_protocol
    }
    if payload.llm_api_key is not None:
        save_data["llm_api_key"] = payload.llm_api_key
    if payload.llm_base_url is not None:
        save_data["llm_base_url"] = payload.llm_base_url
    if payload.asr_provider is not None:
        save_data["asr_provider"] = payload.asr_provider
    if payload.minimax_api_key is not None:
        save_data["minimax_api_key"] = payload.minimax_api_key
    if payload.minimax_base_url is not None:
        save_data["minimax_base_url"] = payload.minimax_base_url

    config.save_settings(save_data)
    return {"code": 0, "message": "Settings updated successfully", "data": payload}

class ListModelsPayload(BaseModel):
    """留空则回退当前已解析的直连提供方（设置页 → ~/.codex/config.toml）"""
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None

@router.post("/list-models")
async def list_models(payload: ListModelsPayload):
    """探测直连端点的可用模型列表（OpenAI 兼容 GET /models），供设置页下拉选择"""
    from app.harness_bridge import llm_client

    base_url = (payload.llm_base_url or "").strip()
    api_key = (payload.llm_api_key or "").strip()
    if not base_url:
        provider = llm_client.resolve_api_provider()
        if not provider:
            return {"code": 1, "message": "未提供 base_url，且当前无已配置的直连提供方", "data": {"models": []}}
        base_url = provider["base_url"]
        api_key = api_key or provider.get("token", "")

    success, models, message = await llm_client.list_models(base_url, token=api_key)
    return {
        "code": 0 if success else 1,
        "message": message,
        "data": {"models": models}
    }

class TestHarnessPayload(BaseModel):
    engine: str = "codex"
    model_override: Optional[str] = None

@router.post("/test-harness")
async def test_harness(payload: TestHarnessPayload):
    from app.harness_bridge.factory import get_harness_by_key
    harness = get_harness_by_key(payload.engine)
    if not harness:
        return {
            "code": 1,
            "message": f"未知的 Harness 引擎: {payload.engine}",
            "data": {
                "success": False,
                "engine": payload.engine,
                "latency_ms": 0.0,
                "active_model": "",
                "message": "引擎不存在"
            }
        }
    
    if hasattr(harness, "ping"):
        success, active_model, latency_ms, msg = await harness.ping(model_override=payload.model_override)
        return {
            "code": 0 if success else 1,
            "message": msg,
            "data": {
                "success": success,
                "engine": payload.engine,
                "latency_ms": round(latency_ms, 1),
                "active_model": active_model,
                "message": msg
            }
        }
    else:
        is_avail = await harness.is_available()
        return {
            "code": 0 if is_avail else 1,
            "message": "就绪" if is_avail else "未就绪",
            "data": {
                "success": is_avail,
                "engine": payload.engine,
                "latency_ms": 1.0,
                "active_model": "内置规则",
                "message": "内置规则引擎就绪" if is_avail else "引擎不可用"
            }
        }

class TestConnectionPayload(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None

@router.post("/test-connection")
async def test_connection(payload: Optional[TestConnectionPayload] = None):
    """
    MiniMax 综合连通性健康探测：
    对 LLM (chat/completions) 和 STT (speech_to_text) 发送轻量探针，
    返回双通道健康状态与精确耗时；若鉴权失败或网络故障抛出 500 明确异常。
    """
    api_key = ""
    base_url = ""
    model = ""
    if payload:
        api_key = (payload.api_key or "").strip()
        base_url = (payload.base_url or "").strip()
        model = (payload.model or "").strip()

    api_key = api_key or config.get_minimax_api_key()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="MiniMax 连通性测试失败: 未配置 MiniMax API Key，请在设置项中输入"
        )

    base_url = normalize_base_url(base_url or config.get_minimax_base_url() or "https://api.minimaxi.com/v1")
    model = model or config.LLM_MODEL or "MiniMax-Text-01"

    headers = {"Authorization": f"Bearer {api_key}"}

    # 1. 探测 LLM 通道
    llm_start = time.time()
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            llm_resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5
                },
                headers=headers,
                timeout=15.0
            )
            llm_latency_ms = round((time.time() - llm_start) * 1000, 1)
            if llm_resp.status_code == 401:
                raise HTTPException(status_code=500, detail=f"MiniMax LLM 鉴权失败 (HTTP 401): {llm_resp.text[:120]}")
            elif llm_resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"MiniMax LLM 接口异常 (HTTP {llm_resp.status_code}): {llm_resp.text[:120]}")
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=500, detail="MiniMax LLM 接口探测超时 (15s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MiniMax LLM 探测异常: {e}")

    # 2. 探测 STT 通道 (speech_to_text)
    stt_start = time.time()
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 6400)
    dummy_wav_bytes = buf.getvalue()
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            stt_resp = await client.post(
                f"{base_url}/speech_to_text",
                headers=headers,
                data={
                    "model": "asr-1.0",
                    "response_format": "verbose_json",
                    "timestamp_level": "word",
                    "stream": "false"
                },
                files={
                    "file": ("probe.wav", dummy_wav_bytes, "audio/wav")
                },
                timeout=15.0
            )
            asr_latency_ms = round((time.time() - stt_start) * 1000, 1)
            if stt_resp.status_code == 401:
                raise HTTPException(status_code=500, detail=f"MiniMax ASR 鉴权失败 (HTTP 401): {stt_resp.text[:120]}")
            elif stt_resp.status_code != 200:
                raise HTTPException(status_code=500, detail=f"MiniMax ASR 接口异常 (HTTP {stt_resp.status_code}): {stt_resp.text[:120]}")
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=500, detail="MiniMax ASR 接口探测超时 (15s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MiniMax ASR 探测异常: {e}")

    return {
        "code": 0,
        "message": "MiniMax 双通道就绪",
        "data": {
            "llm_status": "ok",
            "llm_latency_ms": llm_latency_ms,
            "asr_status": "ok",
            "asr_latency_ms": asr_latency_ms,
            "model_used": model
        }
    }



