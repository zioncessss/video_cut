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

