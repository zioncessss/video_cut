import random
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import STORAGE_DIR, OUTPUTS_DIR
from app.models.entities import (
    CutProject,
    CutProjectStatus,
    SubtitleSegment,
    BrollReplacement,
    MaterialCategory
)
from app.native_engine.storage import storage_service
from app.native_engine.asr_runner import asr_runner
from app.native_engine.keyword_matcher import match_keywords_in_segment
from app.native_engine.ffmpeg_filter import composer
from app.native_engine.subtitle_styler import generate_srt_file
from app.harness_bridge.factory import get_active_harness
from app.harness_bridge.base import HarnessCorrectionRequest

router = APIRouter()

# 内存项目缓存字典
_projects: Dict[str, CutProject] = {}

class AnalyzeAndCutRequest(BaseModel):
    talking_head_id: str
    aspect_ratio: str = "9:16"
    auto_broll: bool = True

class UpdateSubtitlesRequest(BaseModel):
    subtitles: List[Dict[str, Any]]
    broll_replacements: Optional[List[Dict[str, Any]]] = None

@router.post("/analyze-and-cut", response_model=CutProject)
async def analyze_and_cut(req: AnalyzeAndCutRequest):
    talking_head = storage_service.get_material(req.talking_head_id)
    if not talking_head:
        raise HTTPException(status_code=404, detail="口播主视频素材未找到")

    full_th_path = STORAGE_DIR.parent / talking_head.filepath
    if not full_th_path.exists():
        raise HTTPException(status_code=404, detail="口播主视频文件在磁盘上不存在")

    # 1. 固化 ASR 转写
    raw_segments = asr_runner.transcribe(full_th_path)

    # 2. Harness 上下文驾校专有词纠偏
    correction_req = HarnessCorrectionRequest(raw_subtitles=raw_segments)
    correction_res = await get_active_harness().correct_subtitles(correction_req)
    corrected_segments = correction_res.updated_subtitles

    # 3. 关键词匹配与空镜智能分配 (J/L-Cut)
    subtitles: List[SubtitleSegment] = []
    brolls: List[BrollReplacement] = []

    # 预加载各类空镜素材
    venue_materials = storage_service.list_materials(MaterialCategory.VENUE)
    medical_materials = storage_service.list_materials(MaterialCategory.MEDICAL)
    lesson_materials = storage_service.list_materials(MaterialCategory.LESSON)

    cat_map = {
        MaterialCategory.VENUE: venue_materials,
        MaterialCategory.MEDICAL: medical_materials,
        MaterialCategory.LESSON: lesson_materials
    }

    for item in corrected_segments:
        c_text = item.get("corrected_text", "")
        kw_info = match_keywords_in_segment(c_text)
        matched_cat_str = kw_info.get("matched_category")
        matched_cat = MaterialCategory(matched_cat_str) if matched_cat_str else None
        
        assigned_broll_id = None
        if req.auto_broll and matched_cat and cat_map.get(matched_cat):
            # 初始随机选取对应类别的空镜素材
            selected_mat = random.choice(cat_map[matched_cat])
            assigned_broll_id = selected_mat.id
            brolls.append(BrollReplacement(
                start_time=item["start_time"],
                end_time=item["end_time"],
                material_id=selected_mat.id,
                material_category=matched_cat
            ))

        subtitles.append(SubtitleSegment(
            start_time=item["start_time"],
            end_time=item["end_time"],
            raw_text=item.get("raw_text", c_text),
            corrected_text=c_text,
            matched_category=matched_cat,
            matched_keywords=kw_info.get("matched_keywords", []),
            broll_material_id=assigned_broll_id
        ))

    project = CutProject(
        title=f"剪辑_{Path(talking_head.filename).stem}",
        talking_head_id=talking_head.id,
        aspect_ratio=req.aspect_ratio,
        subtitles=subtitles,
        broll_replacements=brolls,
        status=CutProjectStatus.DRAFT
    )
    _projects[project.id] = project
    return project

class CorrectSubtitlesRequest(BaseModel):
    subtitles: List[Dict[str, Any]]
    domain: str = "driving_school"

@router.post("/correct")
async def correct_subtitles_endpoint(req: CorrectSubtitlesRequest):
    correction_req = HarnessCorrectionRequest(
        raw_subtitles=req.subtitles,
        domain_context=req.domain
    )
    result = await get_active_harness().correct_subtitles(correction_req)
    return {
        "code": 0,
        "message": "智能纠偏完成",
        "data": {
            "subtitles": result.updated_subtitles,
            "corrections": [c.model_dump() for c in result.corrections_summary],
            "harness_engine_used": result.harness_engine_used,
            "latency_ms": result.latency_ms
        }
    }

@router.get("/{project_id}", response_model=CutProject)
async def get_project(project_id: str):
    p = _projects.get(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")
    return p

@router.put("/{project_id}/subtitles", response_model=CutProject)
async def update_subtitles(project_id: str, req: UpdateSubtitlesRequest):
    p = _projects.get(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    p.subtitles = [SubtitleSegment(**s) for s in req.subtitles]
    if req.broll_replacements is not None:
        p.broll_replacements = [BrollReplacement(**b) for b in req.broll_replacements]
    _projects[project_id] = p
    return p

@router.post("/{project_id}/render", response_model=CutProject)
async def render_project(project_id: str):
    p = _projects.get(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    th = storage_service.get_material(p.talking_head_id)
    if not th:
        raise HTTPException(status_code=404, detail="口播素材不存在")

    p.status = CutProjectStatus.PROCESSING
    output_filename = f"output_{p.id}_{p.aspect_ratio.replace(':', '_')}.mp4"
    output_path = OUTPUTS_DIR / output_filename

    # 准备空镜物理路径
    broll_cuts_payload = []
    for b in p.broll_replacements:
        m = storage_service.get_material(b.material_id)
        if m:
            full_b_path = STORAGE_DIR.parent / m.filepath
            if full_b_path.exists():
                broll_cuts_payload.append({
                    "start_time": b.start_time,
                    "end_time": b.end_time,
                    "material_path": full_b_path
                })

    full_th_path = STORAGE_DIR.parent / th.filepath
    success = composer.compose_jl_cut(
        talking_head_path=full_th_path,
        broll_cuts=broll_cuts_payload,
        output_path=output_path,
        aspect_ratio=p.aspect_ratio,
        total_duration=th.duration if th.duration > 0 else 15.0
    )

    # 同步生成 SRT 文件
    srt_filename = f"output_{p.id}.srt"
    generate_srt_file([s.model_dump() for s in p.subtitles], OUTPUTS_DIR / srt_filename)

    if success:
        p.status = CutProjectStatus.COMPLETED
        p.output_video_path = f"storage/outputs/{output_filename}"
    else:
        p.status = CutProjectStatus.FAILED

    _projects[project_id] = p
    return p
