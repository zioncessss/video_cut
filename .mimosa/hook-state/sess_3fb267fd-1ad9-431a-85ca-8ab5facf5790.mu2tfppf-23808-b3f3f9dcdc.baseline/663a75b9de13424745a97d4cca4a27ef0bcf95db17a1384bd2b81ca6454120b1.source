from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.harness_bridge.factory import get_active_harness
from app.harness_bridge.base import HarnessInstructionRequest, HarnessPlanResponse
from app.api.editor import _projects

router = APIRouter()

class NaturalInstructionPayload(BaseModel):
    project_id: str
    instruction: str

@router.post("/apply", response_model=HarnessPlanResponse)
async def apply_instruction(payload: NaturalInstructionPayload):
    project = _projects.get(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="剪辑工程不存在")

    req = HarnessInstructionRequest(
        current_project_state=project.model_dump(),
        user_instruction=payload.instruction
    )
    harness = get_active_harness()
    result = await harness.apply_natural_instruction(req)
    
    # 若返回了更新后的状态，同步到工程中
    if result.updated_subtitles:
        project.subtitles = result.updated_subtitles
    if result.updated_brolls:
        project.broll_replacements = result.updated_brolls
    
    _projects[payload.project_id] = project
    return result
