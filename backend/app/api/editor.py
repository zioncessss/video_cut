import secrets
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import STORAGE_DIR, OUTPUTS_DIR, COVERS_DIR, ensure_storage_path
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

        # 1. 固化 ASR 转写与智能合并
        _set_progress(req.talking_head_id, PipelineStage.ASR_TRANSCRIBING, 45, "ASR 语音转写与黄金短句合并中...")
        raw_segments = asr_runner.transcribe(full_th_path)

        # 2. Harness 上下文驾校专有词纠偏
        _set_progress(req.talking_head_id, PipelineStage.LLM_CORRECTING, 75, "大模型行业专名词义智能纠偏中...")
        correction_req = HarnessCorrectionRequest(raw_subtitles=raw_segments)
        correction_res = await get_active_harness().correct_subtitles(correction_req)
        corrected_segments = correction_res.updated_subtitles

        # 3.5 AI 分镜决策（切哪类/时长/转场；不切区与节奏约束由确定性校验兜底）
        scene_decisions: Dict[str, SceneDecision] = {}
        scene_engine_note = "disabled"
        if req.enable_scene_decision:
            _set_progress(req.talking_head_id, PipelineStage.SCENE_DECIDING, 82, "AI 分镜决策中（切分镜/时长/转场）...")
            decision_input = [
                {
                    "id": str(it.get("id")),
                    "text": str(it.get("corrected_text") or it.get("raw_text") or ""),
                    "corrected_text": str(it.get("corrected_text") or it.get("raw_text") or ""),
                    "start_time": float(it.get("start_time", 0.0)),
                    "end_time": float(it.get("end_time", 0.0)),
                }
                for it in corrected_segments
            ]
            try:
                decisions, engine_used, _latency, ok = await get_active_harness().decide_scenes(decision_input)
                if not ok:
                    raise RuntimeError(engine_used)
                scene_decisions = validate_and_clip(decision_input, decisions)
                scene_engine_note = engine_used
            except Exception as sd_err:
                # 真实执行铁律：AI 决策失败如实降级到关键词规则并在 pipeline_notes 标注，不假装成功
                scene_decisions = fallback_keyword_rules(decision_input)
                scene_engine_note = f"keyword-rules (degraded: {str(sd_err)[:120]})"

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

        for item in corrected_segments:
            c_text = item.get("corrected_text", "")
            kw_info = match_keywords_in_segment(c_text)
            matched_cat_str = kw_info.get("matched_category")
            matched_cat = MaterialCategory(matched_cat_str) if matched_cat_str else None

            assigned_broll_id = None
            broll_end = float(item["end_time"])
            sd = scene_decisions.get(str(item.get("id")))
            if sd and sd.broll_category and cat_map.get(sd.broll_category):
                # AI 决策路径：按决策分类随机选素材，窗口 = 句首 + 决策时长
                selected_mat = secrets.choice(cat_map[sd.broll_category])
                assigned_broll_id = selected_mat.id
                if sd.broll_duration > 0:
                    broll_end = min(float(item["start_time"]) + sd.broll_duration, float(item["end_time"]))
                brolls.append(BrollReplacement(
                    start_time=item["start_time"],
                    end_time=broll_end,
                    material_id=selected_mat.id,
                    material_category=sd.broll_category
                ))
                sd.material_id = selected_mat.id
            elif req.auto_broll and matched_cat and cat_map.get(matched_cat):
                # 旧行为兜底（未启用决策或决策未命中）：整句窗口平替
                selected_mat = secrets.choice(cat_map[matched_cat])
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

        project = CutProject(
            title=f"剪辑_{Path(talking_head.filename).stem}",
            talking_head_id=talking_head.id,
            aspect_ratio=req.aspect_ratio,
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
    new_brolls: List[BrollReplacement] = []
    for s in p.subtitles:
        sd = scene_decisions.get(s.id)
        if sd:
            if sd.broll_category:
                mats = storage_service.list_materials(sd.broll_category)
                if mats:
                    m = secrets.choice(mats)
                    sd.material_id = m.id
                    s.broll_material_id = m.id
                    new_brolls.append(BrollReplacement(
                        start_time=s.start_time,
                        end_time=min(s.start_time + sd.broll_duration, s.end_time) if sd.broll_duration > 0 else s.end_time,
                        material_id=m.id,
                        material_category=sd.broll_category
                    ))
                else:
                    sd.reason = (sd.reason + "；该分类暂无素材，自动跳过").strip("；")
                    s.broll_material_id = None
            else:
                s.broll_material_id = None
            s.scene_decision = sd

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

    # 记录前一次的输出文件路径，渲染成功后再安全清理，避免覆盖同名文件产生 Windows 文件句柄锁冲突
    old_output_path = None
    if p.output_video_path:
        old_output_path = (STORAGE_DIR.parent / p.output_video_path).resolve()

    timestamp = int(time.time())
    output_filename = f"output_{p.id}_{p.aspect_ratio.replace(':', '_')}_{timestamp}.mp4"
    output_path = OUTPUTS_DIR / output_filename

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

    # 2. 生成 ASS 高级高亮字幕文件与 SRT 文件
    ass_filename = f"output_{p.id}_{timestamp}.ass"
    ass_path = OUTPUTS_DIR / ass_filename
    generate_ass_file(
        [s.model_dump() for s in p.subtitles],
        ass_path,
        strategy=p.strategy.model_dump()
    )

    srt_filename = f"output_{p.id}_{timestamp}.srt"
    generate_srt_file([s.model_dump() for s in p.subtitles], OUTPUTS_DIR / srt_filename)

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
        p.output_video_path = f"storage/outputs/{output_filename}"
        p.output_absolute_path = str(output_path.resolve())
        p.output_filename = output_filename
        p.output_file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)

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

        ts = int(time.time())
        cover_name = f"cover_{p.id}_{ts}.jpg"
        cover_path = COVERS_DIR / cover_name
        proc = subprocess.run([
            "ffmpeg", "-y",
            "-ss", ss_value,
            "-i", str(full_video),
            "-frames:v", "1", "-q:v", "3",
            str(cover_path)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        if proc.returncode != 0 or not cover_path.exists():
            raise HTTPException(status_code=500, detail="截帧失败：请确认 FFmpeg 可用后重试")
        p.cover_image_path = f"storage/covers/{cover_name}"
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
        ts = int(time.time())
        cover_name = f"cover_{p.id}_{ts}.jpg"
        cover_path = COVERS_DIR / cover_name
        cover_path.write_bytes(img_bytes)
        p.cover_image_path = f"storage/covers/{cover_name}"
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

@router.post("/open-folder")
async def open_folder(req: OpenFolderRequest = OpenFolderRequest()):
    """在系统的文件管理器 (Windows Explorer) 中高亮选中文件或打开导出输出文件夹"""
    import sys
    import subprocess

    target_path = None
    if req.path:
        p = Path(req.path)
        if p.is_absolute():
            target_path = p
        else:
            target_path = (STORAGE_DIR.parent / req.path).resolve()

    if not target_path or not target_path.exists():
        target_path = OUTPUTS_DIR.resolve()

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


