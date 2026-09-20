from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.harness_bridge.factory import get_tier_b_harness
from app.harness_bridge.base import HarnessInstructionRequest, HarnessPlanResponse
from app.models.entities import SubtitleSegment, BrollReplacement
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service

router = APIRouter()

class NaturalInstructionPayload(BaseModel):
    project_id: str
    instruction: str

@router.post("/apply", response_model=HarnessPlanResponse)
async def apply_instruction(payload: NaturalInstructionPayload):
    project = project_storage_service.get_by_project_id(payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="剪辑工程不存在")

    all_materials = storage_service.list_materials()
    mat_meta = [
        {
            "id": m.id,
            "category": m.category.value if hasattr(m.category, "value") else str(m.category),
            "filename": m.filename,
            "duration": m.duration
        }
        for m in all_materials
    ]

    req = HarnessInstructionRequest(
        current_project_state=project.model_dump(),
        user_instruction=payload.instruction,
        available_materials=mat_meta
    )
    harness = get_tier_b_harness()
    try:
        result = await harness.apply_natural_instruction(req)
    except RuntimeError as e:
        # 能力缺失必须诚实反馈：内置词库引擎无开放式指令理解能力，且本机无 codex/zcode 可用
        raise HTTPException(status_code=400, detail=str(e))
    
    # 若返回了更新后的状态，同步并转换为对应实体
    if result.updated_subtitles:
        new_subs = []
        for s in result.updated_subtitles:
            if isinstance(s, dict):
                # 兼容缺少 id 或 raw_text 的情况
                if "id" not in s:
                    s["id"] = f"sub-{len(new_subs)}"
                if "raw_text" not in s:
                    s["raw_text"] = s.get("corrected_text", "")
                if "start_time" not in s:
                    s["start_time"] = 0.0
                if "end_time" not in s:
                    s["end_time"] = 0.0
                new_subs.append(SubtitleSegment(**s))
            elif isinstance(s, SubtitleSegment):
                new_subs.append(s)
        project.subtitles = new_subs
        from app.api.editor import _sync_prune_spans
        _sync_prune_spans(project, force=True)

    if result.updated_brolls:
        new_brolls = []
        for b in result.updated_brolls:
            if isinstance(b, dict):
                if "id" not in b:
                    b["id"] = f"broll-{len(new_brolls)}"
                new_brolls.append(BrollReplacement(**b))
            elif isinstance(b, BrollReplacement):
                new_brolls.append(b)
        project.broll_replacements = new_brolls
    
    project_storage_service.save_project(project)
    return result
