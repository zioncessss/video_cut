from fastapi import APIRouter
from pydantic import BaseModel
import shutil
from typing import Optional
from app.core import config

router = APIRouter()

class SettingsPayload(BaseModel):
    active_harness: str  # "embedded", "codex", "zcode"
    llm_model: str = "GLM-5.3-Flash"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

@router.get("")
async def get_settings():
    has_codex = bool(shutil.which("codex"))
    has_zcode = config.has_zcode_available()
    return {
        "active_harness": config.ACTIVE_HARNESS,
        "llm_model": config.LLM_MODEL,
        "llm_api_key": config.LLM_API_KEY,
        "llm_base_url": config.LLM_BASE_URL,
        "detected_engines": {
            "embedded": True,
            "codex": has_codex,
            "zcode": has_zcode
        },
        "zcode_path": str(config.ZCODE_CLI_PATH) if has_zcode else None
    }

@router.post("")
async def update_settings(payload: SettingsPayload):
    save_data = {
        "active_harness": payload.active_harness,
        "llm_model": payload.llm_model
    }
    if payload.llm_api_key is not None:
        save_data["llm_api_key"] = payload.llm_api_key
    if payload.llm_base_url is not None:
        save_data["llm_base_url"] = payload.llm_base_url
        
    config.save_settings(save_data)
    return {"code": 0, "message": "Settings updated successfully", "data": payload}

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


