from fastapi import APIRouter
from pydantic import BaseModel
import shutil
from app.core import config

router = APIRouter()

class SettingsPayload(BaseModel):
    active_harness: str  # "embedded", "codex", "zcode"
    llm_model: str = "gpt-4o-mini"

@router.get("")
async def get_settings():
    has_codex = bool(shutil.which("codex"))
    has_zcode = bool(shutil.which("zcode"))
    return {
        "active_harness": config.ACTIVE_HARNESS,
        "llm_model": config.LLM_MODEL,
        "detected_engines": {
            "embedded": True,
            "codex": has_codex,
            "zcode": has_zcode
        }
    }

@router.post("")
async def update_settings(payload: SettingsPayload):
    config.ACTIVE_HARNESS = payload.active_harness
    config.LLM_MODEL = payload.llm_model
    return {"code": 0, "message": "Settings updated successfully", "data": payload}
