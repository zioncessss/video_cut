import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import STORAGE_DIR, OUTPUTS_DIR, COVERS_DIR, TASKS_DIR, create_task_dir, ensure_storage_path
import time
from app.models.entities import (
    CutProject,
    CutProjectStatus,
    SubtitleSegment,
    HighlightWord,
    SceneDecision,
    BrollReplacement,
    MaterialCategory,
    EditingStrategy,
    PipelineStage,
    PipelineProgress
)
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.native_engine.asr_runner import asr_runner
from app.native_engine.keyword_matcher import match_keywords_in_segment
from app.native_engine.scene_decision import validate_and_clip, fallback_keyword_rules
from app.native_engine.ffmpeg_filter import composer
from app.native_engine.subtitle_styler import generate_srt_file, generate_ass_file
from app.harness_bridge.factory import get_active_harness
from app.harness_bridge.base import HarnessCorrectionRequest

router = APIRouter()

# 实时进度跟踪字典（供单视频或后续批量任务查询）；按更新时间淘汰最旧条目防止无界增长
_pipeline_progress: Dict[str, PipelineProgress] = {}
_PIPELINE_PROGRESS_MAX = 500

def _set_progress(target_id: str, stage: PipelineStage, percent: int, message: str):
    if len(_pipeline_progress) >= _PIPELINE_PROGRESS_MAX and target_id not in _pipeline_progress:
        oldest_id = min(_pipeline_progress, key=lambda k: _pipeline_progress[k].updated_at)
        _pipeline_progress.pop(oldest_id, None)
    _pipeline_progress[target_id] = PipelineProgress(
        project_id=target_id,
        stage=stage,
        percent=percent,
        message=message,
        updated_at=time.time()
    )

# 兼容保留向后引用的内存映射
_projects = project_storage_service._cache_by_proj_id

class AnalyzeAndCutRequest(BaseModel):
    talking_head_id: str
    aspect_ratio: str = "9:16"
    auto_broll: bool = True
    force_retranscribe: bool = False
    enable_scene_decision: bool = True

class UpdateSubtitlesRequest(BaseModel):
    subtitles: List[Dict[str, Any]]
    broll_replacements: Optional[List[Dict[str, Any]]] = None

def _enrich_project_export_meta(p: CutProject) -> CutProject:
    """如果工程已生成成片，自动补全成片的绝对路径、文件名和文件大小"""
    if p and p.output_video_path:
        full_path = STORAGE_DIR.parent / p.output_video_path
        if full_path.exists():
            p.output_absolute_path = str(full_path.resolve())
            p.output_filename = full_path.name
            p.output_file_size_mb = round(full_path.stat().st_size / (1024 * 1024), 2)
    return p

@router.get("/by-material/{material_id}", response_model=CutProject)
async def get_project_by_material(material_id: str):
    """根据口播视频素材 ID 获取已有持久化工程（若存在则秒级载入缓存）"""
    p = project_storage_service.get_by_material_id(material_id)
    if not p:
        raise HTTPException(status_code=404, detail="该视频素材尚未创建剪辑工程")
    return _enrich_project_export_meta(p)

@router.delete("/by-material/{material_id}")
async def delete_project_by_material(material_id: str):
    """清除某口播视频的持久化工程缓存"""
    success = project_storage_service.delete_project_by_material(material_id)
    return {"code": 0, "message": "已清除该视频的剪辑工程缓存", "deleted": success}

@router.post("/analyze-and-cut", response_model=CutProject)
async def analyze_and_cut(req: AnalyzeAndCutRequest):
    talking_head = storage_service.get_material(req.talking_head_id)
    if not talking_head:
        raise HTTPException(status_code=404, detail="口播主视频素材未找到")

    # 如果非强制重算，且该视频已有持久化缓存工程，则直接加载返回
    if not req.force_retranscribe:
        cached_project = project_storage_service.get_by_material_id(req.talking_head_id)
        if cached_project:
            return _enrich_project_export_meta(cached_project)

    full_th_path = STORAGE_DIR.parent / talking_head.filepath
    if not full_th_path.exists():
        raise HTTPException(status_code=404, detail="口播主视频文件在磁盘上不存在")

    try:
        _set_progress(req.talking_head_id, PipelineStage.AUDIO_EXTRACTING, 15, "正在抽取高质量音频...")

        # 1. 固化 ASR 转写（自然句层，不切割）与智能合并
        _set_progress(req.talking_head_id, PipelineStage.ASR_TRANSCRIBING, 45, "ASR 语音转写中（自然句层）...")
        raw_segments = asr_runner.transcribe(full_th_path)

        # 2. Harness 上下文专有词纠偏（在自然句层面做：完整句模型不会重新断句，
        #    句集一致性守卫不再因句中碎片而触发回退——T038 管线顺序调整）
        _set_progress(req.talking_head_id, PipelineStage.LLM_CORRECTING, 70, "大模型行业专名词义智能纠偏中...")
        correction_req = HarnessCorrectionRequest(raw_subtitles=raw_segments)
        correction_res = await get_active_harness().correct_subtitles(correction_req)

        # 2.5 黄金短句切割：在纠偏后的自然句上执行 6~12 字视读切分
        corrected_segments: List[Dict[str, Any]] = []
        for clause in correction_res.updated_subtitles:
            corrected_segments.extend(asr_runner.split_into_readable_segments([clause]))

        # 3.5 AI 分镜决策（稀疏 Cue Sheet 契约 + 双层 60%~70% 黄金编排）
        scene_decisions: Dict[str, SceneDecision] = {}
        scene_engine_note = "disabled"
        planned_windows: List[Dict[str, Any]] = []

        th_duration = float(talking_head.duration or 0.0)
        if th_duration <= 0:
            th_duration = max((float(it.get("end_time", 0.0)) for it in corrected_segments), default=60.0)

        target_cov = req.strategy.broll_target_coverage if hasattr(req, "strategy") and req.strategy else 0.65

        from app.native_engine.scene_decision import (
            plan_dual_layer_broll,
            fallback_keyword_rules,
            validate_and_clip,
            BrollCueItem
        )

        decision_input = [
            {
                "id": str(it.get("id")),
                "text": str(it.get("corrected_text") or it.get("raw_text") or ""),
                "corrected_text": str(it.get("corrected_text") or it.get("raw_text") or ""),
                "start_time": float(it.get("start_time", 0.0)),
                "end_time": float(it.get("end_time", 0.0)),
                "words": it.get("words", [])
            }
            for it in corrected_segments
        ]

        if req.enable_scene_decision:
            _set_progress(req.talking_head_id, PipelineStage.SCENE_DECIDING, 82, "AI 分镜决策中（稀疏指示清单与双层黄金编排）...")
            try:
                cues_or_decisions, engine_used, _latency, ok = await get_active_harness().decide_scenes(decision_input)
                if not ok:
                    raise RuntimeError(engine_used)
                scene_engine_note = engine_used

                if cues_or_decisions and isinstance(cues_or_decisions[0], BrollCueItem):
                    planned_windows = plan_dual_layer_broll(
                        subtitles=decision_input,
                        cues=cues_or_decisions,
                        total_duration=th_duration,
                        target_coverage=target_cov
                    )
                elif cues_or_decisions and isinstance(cues_or_decisions[0], dict):
                    sd_map = validate_and_clip(decision_input, cues_or_decisions)
                    raw_cues = [
                        BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
                        for s in decision_input if (sd := sd_map.get(s["id"])) and sd.broll_category
                    ]
                    planned_windows = plan_dual_layer_broll(
                        subtitles=decision_input,
                        cues=raw_cues,
                        total_duration=th_duration,
                        target_coverage=target_cov
                    )
                else:
                    planned_windows = plan_dual_layer_broll(
                        subtitles=decision_input,
                        cues=[],
                        total_duration=th_duration,
                        target_coverage=target_cov
                    )
            except Exception as sd_err:
                # 真实执行铁律：AI 决策失败如实降级到关键词规则并在 pipeline_notes 标注，不假装成功
                scene_engine_note = f"keyword-rules (degraded: {str(sd_err)[:120]})"
                scene_decisions = fallback_keyword_rules(decision_input, total_duration=th_duration, target_coverage=target_cov)
                raw_cues = [
                    BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
                    for s in decision_input if (sd := scene_decisions.get(s["id"])) and sd.broll_category
                ]
                planned_windows = plan_dual_layer_broll(
                    subtitles=decision_input,
                    cues=raw_cues,
                    total_duration=th_duration,
                    target_coverage=target_cov
                )
        elif req.auto_broll:
            # 未开启大模型决策但开启自动空镜：直接走关键词规则 + 双层铺底
            scene_decisions = fallback_keyword_rules(decision_input, total_duration=th_duration, target_coverage=target_cov)
            raw_cues = [
                BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
                for s in decision_input if (sd := scene_decisions.get(s["id"])) and sd.broll_category
            ]
            planned_windows = plan_dual_layer_broll(
                subtitles=decision_input,
                cues=raw_cues,
                total_duration=th_duration,
                target_coverage=target_cov
            )

        # 4. 关键词匹配与空镜智能分配 (J/L-Cut)
        _set_progress(req.talking_head_id, PipelineStage.BROLL_MATCHING, 90, "关键词视读匹配与空镜对齐中...")
        subtitles: List[SubtitleSegment] = []
        brolls: List[BrollReplacement] = []

        # 预加载各类空镜素材
        venue_materials = storage_service.list_materials(MaterialCategory.VENUE)
        experience_materials = storage_service.list_materials(MaterialCategory.EXPERIENCE)
        lesson_materials = storage_service.list_materials(MaterialCategory.LESSON)

        cat_map = {
            MaterialCategory.VENUE: venue_materials,
            MaterialCategory.EXPERIENCE: experience_materials,
            MaterialCategory.LESSON: lesson_materials
        }

        # 实例化最终 broll 替换
        for w in planned_windows:
            mats = cat_map.get(w["material_category"]) or []
            if not mats:
                continue
            m = secrets.choice(mats)
            brolls.append(BrollReplacement(
                start_time=w["start_time"],
                end_time=w["end_time"],
                material_id=m.id,
                material_category=w["material_category"]
            ))

        for item in corrected_segments:
            c_text = item.get("corrected_text", "")
            kw_info = match_keywords_in_segment(c_text)
            matched_cat_str = kw_info.get("matched_category")
            matched_cat = MaterialCategory(matched_cat_str) if matched_cat_str else None

            # 判定该字幕是否落在某个空镜窗口内
            assigned_broll_id = None
            assigned_cat = None
            assigned_dur = 0.0
            mid = (float(item["start_time"]) + float(item["end_time"])) / 2.0
            for b in brolls:
                if b.start_time <= mid <= b.end_time:
                    assigned_broll_id = b.material_id
                    assigned_cat = b.material_category
                    assigned_dur = round(b.end_time - b.start_time, 2)
                    break

            sd = scene_decisions.get(str(item.get("id")))
            if not sd:
                sd = SceneDecision(
                    part="body",
                    broll_category=assigned_cat,
                    broll_duration=assigned_dur,
                    material_id=assigned_broll_id,
                    reason="双层黄金编排分镜" if assigned_cat else "保留口播真人画面"
                )
            elif assigned_broll_id:
                sd.material_id = assigned_broll_id

            subtitles.append(SubtitleSegment(
                start_time=item["start_time"],
                end_time=item["end_time"],
                raw_text=item.get("raw_text", c_text),
                corrected_text=c_text,
                matched_category=matched_cat,
                matched_keywords=kw_info.get("matched_keywords", []),
                highlight_words=[
                    HighlightWord(**w) for w in (item.get("highlight_words") or [])
                    if isinstance(w, dict) and w.get("word")
                ],
                scene_decision=sd,
                broll_material_id=assigned_broll_id
            ))

        summary_list = [c.model_dump() for c in correction_res.corrections_summary] if hasattr(correction_res, 'corrections_summary') else []
        engine_name = correction_res.harness_engine_used if hasattr(correction_res, 'harness_engine_used') else "codex"
        latency_val = correction_res.latency_ms if hasattr(correction_res, 'latency_ms') else 0.0

        # 独立工程文件夹：每个待剪口播视频进入剪辑阶段自动安排专属目录 YYYYMMDD_HHMMSS_{title}
        task_dir_path = create_task_dir(Path(talking_head.filename).stem)
        task_dir_rel = str(task_dir_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/")

        project = CutProject(
            title=f"剪辑_{Path(talking_head.filename).stem}",
            talking_head_id=talking_head.id,
            aspect_ratio=req.aspect_ratio,
            task_dir=task_dir_rel,
            subtitles=subtitles,
            broll_replacements=brolls,
            raw_asr_segments=raw_segments,
            status=CutProjectStatus.DRAFT,
            corrections_summary=summary_list,
            pipeline_notes={"scene_decision_engine": scene_engine_note, "scene_decision_degraded": scene_engine_note.startswith("keyword-rules")},
            last_engine_used=engine_name,
            correction_latency_ms=latency_val
        )
        project_storage_service.save_project(project)
        _set_progress(project.id, PipelineStage.COMPLETED, 100, "智能初剪与纠偏已完成")
        _set_progress(req.talking_head_id, PipelineStage.COMPLETED, 100, "智能初剪与纠偏已完成")
        return project
    except Exception as e:
        _set_progress(req.talking_head_id, PipelineStage.FAILED, 0, f"初剪失败: {str(e)}")
        raise e

@router.get("/{project_id}/progress", response_model=PipelineProgress)
async def get_project_progress(project_id: str):
    """获取剪辑任务实时处理进度估算（为单视频剪辑与后续批量剪辑进度条预留数据接口）"""
    if project_id in _pipeline_progress:
        return _pipeline_progress[project_id]
    return PipelineProgress(
        project_id=project_id,
        stage=PipelineStage.IDLE,
        percent=0,
        message="空闲或就绪"
    )

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

class SceneDecisionRequest(BaseModel):
    subtitle_ids: Optional[List[str]] = None  # 缺省=全部句子

@router.post("/{project_id}/scene-decision")
async def redecide_scenes(project_id: str, req: SceneDecisionRequest = SceneDecisionRequest()):
    """对既有工程单独重跑 AI 分镜决策（不重转写）；失败降级关键词规则并如实标注"""
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    decision_input = [
        {
            "id": s.id,
            "text": s.corrected_text,
            "corrected_text": s.corrected_text,
            "start_time": s.start_time,
            "end_time": s.end_time,
        }
        for s in p.subtitles
        if not req.subtitle_ids or s.id in req.subtitle_ids
    ]
    if not decision_input:
        raise HTTPException(status_code=400, detail="没有匹配的字幕句")

    try:
        decisions, engine_used, latency, ok = await get_active_harness().decide_scenes(decision_input)
        if not ok:
            raise RuntimeError(engine_used)
        scene_decisions = validate_and_clip(decision_input, decisions)
        degraded = False
    except Exception as e:
        scene_decisions = fallback_keyword_rules(decision_input)
        engine_used = f"keyword-rules (degraded: {str(e)[:120]})"
        degraded = True

    # 依据新决策整体重建空镜窗口（随机落定素材），并持久化到字幕与工程
    # 依据决策产出原始窗口，经编排层稳定化（合并防闪/单镜 2~6s 钳制/覆盖率收敛约六成）后再随机选材
    raw_spans: List[Dict[str, Any]] = []
    for s in p.subtitles:
        sd = scene_decisions.get(s.id)
        if not sd:
            continue
        s.scene_decision = sd
        if sd.broll_category and sd.broll_duration > 0:
            raw_spans.append({
                "start_time": s.start_time,
                "end_time": min(s.start_time + sd.broll_duration, s.end_time) if sd.broll_duration > 0 else s.end_time,
                "material_category": sd.broll_category
            })

    total_duration = max((s.end_time for s in p.subtitles), default=0.0)
    from app.native_engine.scene_decision import plan_stable_windows
    planned = plan_stable_windows(raw_spans, total_duration=total_duration)

    new_brolls: List[BrollReplacement] = []
    for w in planned:
        mats = storage_service.list_materials(w["material_category"]) or []
        if not mats:
            continue
        m = secrets.choice(mats)
        new_brolls.append(BrollReplacement(
            start_time=w["start_time"],
            end_time=w["end_time"],
            material_id=m.id,
            material_category=w["material_category"]
        ))

    # 字幕归窗：中点落在某分镜窗口内的字幕，关联该窗口素材
    for s in p.subtitles:
        s.broll_material_id = None
        mid = (s.start_time + s.end_time) / 2
        for b in new_brolls:
            if b.start_time > mid:
                break
            if b.start_time <= mid <= b.end_time:
                s.broll_material_id = b.material_id
                sd = scene_decisions.get(s.id)
                if sd:
                    sd.material_id = b.material_id
                break

    p.broll_replacements = new_brolls
    p.pipeline_notes = {**(p.pipeline_notes or {}), "scene_decision_engine": engine_used, "scene_decision_degraded": degraded}
    project_storage_service.save_project(p)

    return {
        "code": 0,
        "data": {
            "subtitles": [
                {"id": s.id, "scene_decision": (s.scene_decision.model_dump() if s.scene_decision else None)}
                for s in p.subtitles
            ],
            "engine_used": engine_used,
            "latency_ms": round(latency, 1),
            "degraded": degraded
        }
    }

@router.get("/{project_id}", response_model=CutProject)
async def get_project(project_id: str):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")
    return _enrich_project_export_meta(p)

@router.put("/{project_id}/subtitles", response_model=CutProject)
async def update_subtitles(project_id: str, req: UpdateSubtitlesRequest):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    p.subtitles = [SubtitleSegment(**s) for s in req.subtitles]
    if req.broll_replacements is not None:
        p.broll_replacements = [BrollReplacement(**b) for b in req.broll_replacements]
    project_storage_service.save_project(p)
    return p

@router.put("/{project_id}/strategy", response_model=CutProject)
async def update_strategy(project_id: str, strategy: EditingStrategy):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    p.strategy = strategy
    project_storage_service.save_project(p)
    return p

@router.post("/{project_id}/render", response_model=CutProject)
async def render_project(project_id: str):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    th = storage_service.get_material(p.talking_head_id)
    if not th:
        raise HTTPException(status_code=404, detail="口播素材不存在")

    p.status = CutProjectStatus.PROCESSING

    # 独立工程目录：确保专属目录存在，所有渲染成果（成片、字幕、音频、封面）落入独立目录
    if not p.task_dir:
        stem_name = Path(th.filename).stem if th.filename else "clip"
        task_dir_path = create_task_dir(stem_name)
        p.task_dir = str(task_dir_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/")

    target_task_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
    target_task_dir.mkdir(parents=True, exist_ok=True)

    # 记录前一次的输出文件路径，渲染成功后再安全清理，避免覆盖同名文件产生 Windows 文件句柄锁冲突
    old_output_path = None
    if p.output_video_path:
        old_output_path = (STORAGE_DIR.parent / p.output_video_path).resolve()

    timestamp = int(time.time())
    output_filename = f"output_{p.id}_{p.aspect_ratio.replace(':', '_')}_{timestamp}.mp4"
    output_path = target_task_dir / output_filename

    # 1. 如果用户策略设为纯口播 (talking_only)，清空参与渲染的空镜
    broll_cuts_payload = []
    if p.strategy.broll_pacing != "talking_only":
        for b in p.broll_replacements:
            m = storage_service.get_material(b.material_id)
            if m:
                full_b_path = STORAGE_DIR.parent / m.filepath
                if full_b_path.exists():
                    # 附带该窗口对应字幕的分镜转场时长（fade 档由合成器消费）
                    transition_seconds = 0.0
                    for s in p.subtitles:
                        if s.start_time == b.start_time and s.scene_decision:
                            transition_seconds = s.scene_decision.transition_seconds
                            break
                    broll_cuts_payload.append({
                        "start_time": b.start_time,
                        "end_time": b.end_time,
                        "material_path": full_b_path,
                        "transition": transition_seconds
                    })

    # 2. 生成 ASS 高级高亮字幕文件与 SRT 文件至专属任务目录
    ass_path = target_task_dir / "subtitles.ass"
    generate_ass_file(
        [s.model_dump() for s in p.subtitles],
        ass_path,
        strategy=p.strategy.model_dump()
    )

    srt_path = target_task_dir / "subtitles.srt"
    generate_srt_file([s.model_dump() for s in p.subtitles], srt_path)

    # 3. 复合渲染：空镜平替 + ASS字幕 + 顶部横幅 + 水印
    full_th_path = STORAGE_DIR.parent / th.filepath
    try:
        success = composer.compose_jl_cut(
            talking_head_path=full_th_path,
            broll_cuts=broll_cuts_payload,
            output_path=output_path,
            aspect_ratio=p.aspect_ratio,
            total_duration=th.duration if th.duration > 0 else 15.0,
            ass_subtitle_path=ass_path,
            strategy=p.strategy.model_dump()
        )
    except Exception as e:
        # 真实执行铁律：合成失败必须如实暴露，工程状态落库为 FAILED，并带回真实错误详情
        p.status = CutProjectStatus.FAILED
        project_storage_service.save_project(p)
        raise HTTPException(status_code=500, detail=f"视频合成失败: {str(e)}")

    if success and output_path.exists():
        p.status = CutProjectStatus.COMPLETED
        p.output_video_path = f"{p.task_dir}/{output_filename}"
        p.output_absolute_path = str(output_path.resolve())
        p.output_filename = output_filename
        p.output_file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)

        # 自动抽取 0.5s 默认封面帧（若尚未生成封面），便于在成片网格中直接显示缩略图
        if not p.cover_image_path:
            try:
                import subprocess
                cover_dest = target_task_dir / "cover.jpg"
                c_proc = subprocess.run([
                    "ffmpeg", "-y", "-ss", "0.500", "-i", str(output_path),
                    "-frames:v", "1", "-q:v", "3", str(cover_dest)
                ], capture_output=True, timeout=10)
                if c_proc.returncode == 0 and cover_dest.exists():
                    p.cover_image_path = f"{p.task_dir}/cover.jpg"
                    p.cover_source = "frame"
            except Exception as e:
                print(f"[render] 自动抽取封面跳过: {e}")

        # 安全清理上一版渲染产物，防止磁盘膨胀，若被播放器占用则静默忽略
        if old_output_path and old_output_path.exists() and old_output_path != output_path.resolve():
            try:
                old_output_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"[render] 保留旧渲染文件 (可能正在被播放): {e}")
    else:
        p.status = CutProjectStatus.FAILED

    project_storage_service.save_project(p)
    return p

class CoverRequest(BaseModel):
    source: str = "frame"             # frame | upload | ai
    timestamp: Optional[float] = None  # source=frame 时必填：成片内秒数
    image_base64: Optional[str] = None  # source=upload 时：图片 base64 内容

@router.post("/{project_id}/cover")
async def set_project_cover(project_id: str, req: CoverRequest):
    """设置工程封面：成片截帧 / 本地上传；AI 生成仅规划占位，显式 501 不伪造结果"""
    import base64 as _b64
    import re as _re
    import subprocess

    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    if req.source == "ai":
        raise HTTPException(status_code=501, detail="AI 封面生成规划中，敬请期待")

    # 确定保存封面的目标目录：若有独立任务目录优先保存在专属目录
    if p.task_dir:
        target_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        cover_name = "cover.jpg"
        cover_path = target_dir / cover_name
        rel_cover = f"{p.task_dir}/{cover_name}"
    else:
        ts = int(time.time())
        cover_name = f"cover_{p.id}_{ts}.jpg"
        cover_path = COVERS_DIR / cover_name
        rel_cover = f"storage/covers/{cover_name}"

    if req.source == "frame":
        if not p.output_video_path:
            raise HTTPException(status_code=400, detail="该工程尚未生成成片，无法截帧")
        if req.timestamp is None:
            raise HTTPException(status_code=400, detail="请提供有效的截帧时间点 timestamp")
        # 路径守卫：规范化并校验必须位于 storage 目录内，之后才允许进入命令参数
        full_video = ensure_storage_path(STORAGE_DIR.parent / p.output_video_path)
        if not full_video.exists():
            raise HTTPException(status_code=404, detail="成片文件在磁盘上不存在")

        # 白名单清洗：时间点只能是纯数字秒值，不合法时回退首帧 0.000
        ss_value = f"{max(0.0, min(float(req.timestamp), 36000.0)):.3f}"
        if not _re.fullmatch(r"\d+\.\d{3}", ss_value):
            ss_value = "0.000"

        proc = subprocess.run([
            "ffmpeg", "-y",
            "-ss", ss_value,
            "-i", str(full_video),
            "-frames:v", "1", "-q:v", "3",
            str(cover_path)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode != 0 or not cover_path.exists():
            raise HTTPException(status_code=500, detail="截帧失败：请确认 FFmpeg 可用后重试")
        p.cover_image_path = rel_cover
        p.cover_source = "frame"
    elif req.source == "upload":
        if not req.image_base64:
            raise HTTPException(status_code=400, detail="请上传图片内容 image_base64")
        try:
            img_bytes = _b64.b64decode(req.image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="图片 base64 解码失败")
        if len(img_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片超过 10MB 上限")
        cover_path.write_bytes(img_bytes)
        p.cover_image_path = rel_cover
        p.cover_source = "upload"
    else:
        raise HTTPException(status_code=400, detail=f"不支持的封面来源: {req.source}")

    project_storage_service.save_project(p)
    return {
        "code": 0,
        "data": {
            "cover_image_path": p.cover_image_path,
            "cover_source": p.cover_source,
            "cover_url": f"/{p.cover_image_path}"
        }
    }

class OpenFolderRequest(BaseModel):
    path: Optional[str] = None
    project_id: Optional[str] = None

@router.post("/open-folder")
async def open_folder(req: OpenFolderRequest = OpenFolderRequest()):
    """在系统的文件管理器 (Windows Explorer) 中高亮选中文件或打开独立任务文件夹"""
    import sys
    import subprocess

    target_path = None
    if req.project_id:
        p = project_storage_service.get_by_project_id(req.project_id)
        if p:
            if p.task_dir:
                td = (STORAGE_DIR.parent / p.task_dir).resolve()
                if td.exists():
                    target_path = td
            if not target_path and p.output_video_path:
                vp = (STORAGE_DIR.parent / p.output_video_path).resolve()
                if vp.exists():
                    target_path = vp
    elif req.path:
        p = Path(req.path)
        if p.is_absolute():
            target_path = p
        else:
            target_path = (STORAGE_DIR.parent / req.path).resolve()

    if not target_path or not target_path.exists():
        target_path = TASKS_DIR.resolve() if TASKS_DIR.exists() else OUTPUTS_DIR.resolve()

    try:
        if sys.platform == "win32":
            clean_path = str(target_path.resolve()).replace('/', '\\')
            if target_path.is_file():
                subprocess.Popen(["explorer.exe", f"/select,{clean_path}"])
            else:
                subprocess.Popen(["explorer.exe", clean_path])
        elif sys.platform == "darwin":
            if target_path.is_file():
                subprocess.Popen(["open", "-R", str(target_path)])
            else:
                subprocess.Popen(["open", str(target_path)])
        else:
            folder = target_path.parent if target_path.is_file() else target_path
            subprocess.Popen(["xdg-open", str(folder)])
        return {"code": 0, "message": "已成功唤起文件管理器", "path": str(target_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件目录失败: {str(e)}")

@router.get("", response_model=List[CutProject])
async def list_projects():
    """获取所有剪辑工程列表（供成片网格、快速切换、状态展示）"""
    projects = project_storage_service.list_all_projects()
    return [_enrich_project_export_meta(p) for p in projects]


