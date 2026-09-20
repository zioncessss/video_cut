import copy
import json
import re
import secrets
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from app.core.config import STORAGE_DIR, OUTPUTS_DIR, COVERS_DIR, TASKS_DIR, create_task_dir, ensure_storage_path, apply_glossary_corrections
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
    PipelineProgress,
    PruneSpan,
    PruneReason,
)
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.native_engine.asr_runner import asr_runner
from app.native_engine.keyword_matcher import match_keywords_in_segment, build_highlight_words
from app.native_engine.scene_decision import validate_and_clip, fallback_keyword_rules
from app.native_engine.ffmpeg_filter import composer
from app.native_engine.subtitle_styler import generate_srt_file, generate_ass_file
from app.harness_bridge.factory import get_active_harness
from app.harness_bridge.base import HarnessCorrectionRequest

router = APIRouter()

def extract_cover_frame(source_video_path: Path, output_cover_path: Path, timestamp: float = 0.5) -> bool:
    """从指定视频文件中快速截取高质量静止帧作为封面（耗时通常 <50ms）"""
    if not source_video_path.exists():
        return False
    try:
        import subprocess
        c_proc = subprocess.run([
            "ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(source_video_path),
            "-frames:v", "1", "-q:v", "3", str(output_cover_path)
        ], capture_output=True, timeout=10)
        return c_proc.returncode == 0 and output_cover_path.exists()
    except Exception as ce:
        print(f"[extract_cover_frame] 截取封面异常: {ce}")
        return False

def _prepare_render_subtitles(subtitles: list, speed: float = 1.0, kept_spans: Optional[list] = None) -> list:
    """
    1. 过滤已标记剔除的字幕（is_pruned == True）
    2. 若有 kept_spans（粗剪紧凑时间轴），将有效起止时间精确重投影至紧凑时间轴
    3. 如果倍速不为 1.0，等比缩放字幕起止时间与词级时间戳，避免浮点漂移
    """
    from app.native_engine.prune_engine import auto_prune_engine

    speed = float(speed or 1.0)
    result = []

    for s in subtitles:
        data = s.model_dump() if hasattr(s, "model_dump") else dict(s)
        # 1. 过滤被剔除的句子
        if data.get("is_pruned"):
            continue

        item = copy.deepcopy(data)
        st = float(item["start_time"])
        et = float(item["end_time"])

        # 2. 紧凑时间轴重投影
        if kept_spans:
            mapped = auto_prune_engine.map_interval_to_compact(st, et, kept_spans)
            if not mapped:
                continue
            item["start_time"], item["end_time"] = mapped
            if "words" in item and isinstance(item["words"], list):
                mapped_words = []
                for w in item["words"]:
                    w_dict = w.model_dump() if hasattr(w, "model_dump") else dict(w)
                    if w_dict.get("start") is not None and w_dict.get("end") is not None:
                        w_mapped = auto_prune_engine.map_interval_to_compact(float(w_dict["start"]), float(w_dict["end"]), kept_spans)
                        if w_mapped:
                            w_dict["start"], w_dict["end"] = w_mapped
                            mapped_words.append(w_dict)
                item["words"] = mapped_words

        # 3. 倍速处理
        if abs(speed - 1.0) >= 0.01:
            item["start_time"] = round(float(item["start_time"]) / speed, 3)
            item["end_time"] = round(float(item["end_time"]) / speed, 3)
            if "words" in item and isinstance(item["words"], list):
                for w in item["words"]:
                    if isinstance(w, dict):
                        if w.get("start") is not None:
                            w["start"] = round(float(w["start"]) / speed, 3)
                        if w.get("end") is not None:
                            w["end"] = round(float(w["end"]) / speed, 3)

        result.append(item)
    return result

def _save_task_manifest(task_dir_path: Path, project: CutProject):
    """在任务专属目录中生成自包含的索引清单 project_manifest.json"""
    try:
        out_fn = project.output_filename or (Path(project.output_video_path).name if project.output_video_path else None)
        manifest_data = {
            "project_id": project.id,
            "title": project.title,
            "aspect_ratio": project.aspect_ratio,
            "status": project.status.value if hasattr(project.status, "value") else str(project.status),
            "talking_head_id": project.talking_head_id,
            "task_dir": project.task_dir,
            "output_video_path": project.output_video_path,
            "output_filename": out_fn,
            "output_file_size_mb": project.output_file_size_mb,
            "cover_image_path": project.cover_image_path,
            "cover_source": project.cover_source,
            "subtitles_count": len(project.subtitles),
            "broll_count": len(project.broll_replacements),
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "last_rendered_at": datetime.now().isoformat(),
            "files": {
                "output_video": out_fn,
                "cover_image": Path(project.cover_image_path).name if project.cover_image_path else None,
                "subtitles_ass": "subtitles.ass" if (task_dir_path / "subtitles.ass").exists() else None,
                "subtitles_srt": "subtitles.srt" if (task_dir_path / "subtitles.srt").exists() else None,
            }
        }
        manifest_file = task_dir_path / "project_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[_save_task_manifest] 保存 manifest 异常: {e}")

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
    enable_llm_correction: bool = False  # 默认为 False：高精 ASR 直通模式，仅走词库确定性兜底，避免 LLM 过度干预与篡改
    video_speed: float = 1.0
    auto_render: bool = False  # 默认为 False：单视频交互初剪极速秒级进入实时编辑；为 True 时（如批量全自动流水线）同步压制最终成片

class UpdateSubtitlesRequest(BaseModel):
    subtitles: List[Dict[str, Any]]
    broll_replacements: Optional[List[Dict[str, Any]]] = None

def _sync_prune_spans(p: CutProject, force: bool = False) -> bool:
    """
    联动粗剪区间计算：
    - 若开启了智能粗剪 (enable_auto_prune)，且 (force 或 prune_spans 为空)，自动基于当前字幕与素材时长计算 prune_spans 与 compact_subtitles
    - 若关闭了智能粗剪，清理自动生成的 prune_spans，仅保留手动标记的片段
    返回是否有数据变更
    """
    from app.native_engine.prune_engine import auto_prune_engine

    if not p.strategy.enable_auto_prune:
        manual_spans = [s for s in (p.prune_spans or []) if s.reason == PruneReason.MANUAL.value and s.is_active]
        if len(p.prune_spans or []) != len(manual_spans):
            p.prune_spans = manual_spans
            for sub in p.subtitles:
                if not any(s.source_subtitle_id == sub.id for s in manual_spans):
                    sub.is_pruned = False
                    sub.prune_reason = None
            th = storage_service.get_material(p.talking_head_id)
            th_dur = float(th.duration if th and th.duration and th.duration > 0 else 15.0)
            if manual_spans:
                kept = auto_prune_engine.compute_kept_spans(th_dur, manual_spans)
                p.compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept)
            else:
                p.compact_subtitles = [s for s in p.subtitles if not s.is_pruned]
            return True
        return False

    if not p.subtitles:
        return False

    has_auto_spans = any(s.reason != PruneReason.MANUAL.value for s in (p.prune_spans or []))
    if not force and has_auto_spans and len(p.prune_spans or []) > 0:
        return False

    th = storage_service.get_material(p.talking_head_id)
    th_dur = float(th.duration if th and th.duration and th.duration > 0 else 15.0)
    prune_cfg = {
        "enable_head_prune": p.strategy.enable_head_prune,
        "enable_tail_prune": p.strategy.enable_tail_prune,
        "enable_retake_prune": p.strategy.enable_retake_prune,
        "enable_mid_silence_prune": p.strategy.enable_mid_silence_prune,
        "head_padding_seconds": p.strategy.head_padding_seconds,
        "tail_padding_seconds": p.strategy.tail_padding_seconds,
        "mid_silence_threshold": p.strategy.mid_silence_threshold,
        "mid_silence_breath_gap": p.strategy.mid_silence_breath_gap,
        "retake_pause_min": p.strategy.retake_pause_min,
        "retake_similarity_min": p.strategy.retake_similarity_min,
    }
    new_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=p.subtitles,
        video_duration=th_dur,
        config=prune_cfg
    )

    manual_spans = [s for s in (p.prune_spans or []) if s.reason == PruneReason.MANUAL.value and s.is_active]
    p.prune_spans = new_spans + [s for s in manual_spans if not any(ns.id == s.id for ns in new_spans)]

    for sub in p.subtitles:
        if any(s.source_subtitle_id == sub.id for s in manual_spans):
            sub.is_pruned = True
            sub.prune_reason = PruneReason.MANUAL.value
        elif sub.id in pruned_ids:
            sub.is_pruned = True
            sub.prune_reason = PruneReason.RETAKE_DISCARD.value
        else:
            sub.is_pruned = False
            sub.prune_reason = None

    active_spans = [s for s in p.prune_spans if s.is_active]
    kept = auto_prune_engine.compute_kept_spans(th_dur, active_spans)
    p.compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept)
    return True

def _enrich_project_export_meta(p: CutProject) -> CutProject:
    """真实性守卫与元数据补全：校验成片与封面磁盘存在性，若被外部清理则自愈防御，杜绝死引用与黑屏"""
    if not p:
        return p

    # 1. 成片物理文件检测：若成片已被物理清理或移动，如实同步状态，绝不伪造
    if p.output_video_path:
        full_path = (STORAGE_DIR.parent / p.output_video_path).resolve()
        if full_path.exists() and full_path.is_file():
            p.output_absolute_path = str(full_path.resolve())
            p.output_filename = full_path.name
            p.output_file_size_mb = round(full_path.stat().st_size / (1024 * 1024), 2)
        else:
            p.output_video_path = None
            p.output_absolute_path = None
            p.output_filename = None
            p.output_file_size_mb = None
            if p.status == CutProjectStatus.COMPLETED:
                p.status = CutProjectStatus.DRAFT

    # 2. 封面健壮性检测与自动自愈：若封面不存在，自动从口播原素材抽取 0.5s 封面帧
    has_valid_cover = False
    if p.cover_image_path:
        full_cover = (STORAGE_DIR.parent / p.cover_image_path).resolve()
        if full_cover.exists() and full_cover.is_file() and full_cover.stat().st_size > 0:
            has_valid_cover = True

    if not has_valid_cover and p.talking_head_id:
        try:
            th = storage_service.get_material(p.talking_head_id)
            if th and th.filepath:
                full_th = (STORAGE_DIR.parent / th.filepath).resolve()
                if full_th.exists() and full_th.is_file():
                    if p.task_dir:
                        cov_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
                    else:
                        cov_dir = (STORAGE_DIR / "covers").resolve()
                    cov_dir.mkdir(parents=True, exist_ok=True)
                    target_cover_path = cov_dir / "cover.jpg"
                    if extract_cover_frame(full_th, target_cover_path, timestamp=0.5):
                        rel_path = str(target_cover_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/")
                        p.cover_image_path = rel_path
                        p.cover_source = "frame"
                        project_storage_service.save_project(p)
        except Exception as e:
            print(f"[_enrich_project_export_meta] 自动恢复封面失败: {e}")

    # 3. 动态检查并同步智能粗剪区间与紧凑时间轴
    changed = _sync_prune_spans(p, force=False)
    if changed:
        try:
            project_storage_service.save_project(p)
        except Exception as se:
            print(f"[_enrich_project_export_meta] 保存粗剪区间异常: {se}")

    active_spans = [s for s in (p.prune_spans or []) if s.is_active]
    if active_spans:
        from app.native_engine.prune_engine import auto_prune_engine
        th = storage_service.get_material(p.talking_head_id)
        th_dur = float(th.duration if th and th.duration else 15.0)
        kept = auto_prune_engine.compute_kept_spans(th_dur, active_spans)
        p.compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept)
    else:
        p.compact_subtitles = [s for s in p.subtitles if not s.is_pruned]

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

        # 2. 字幕处理（支持高精 ASR 直通模式，杜绝大模型过度纠偏）：
        #    若开启 enable_llm_correction 则走大模型纠偏；
        #    默认高精 ASR 直通：直接以 ASR 原文为主 + 本地词库确定性兜底（0 延迟、0 幻觉、无过度改写）
        if req.enable_llm_correction:
            _set_progress(req.talking_head_id, PipelineStage.LLM_CORRECTING, 70, "大模型行业专名词义智能纠偏中...")
            correction_req = HarnessCorrectionRequest(raw_subtitles=raw_segments)
            correction_res = await get_active_harness().correct_subtitles(correction_req)
            candidate_subs = correction_res.updated_subtitles
            summary_list = [
                c.model_dump() for c in (getattr(correction_res, 'corrections_summary', []) or [])
                if hasattr(c, 'original_text') and hasattr(c, 'corrected_text') and c.original_text.strip() != c.corrected_text.strip()
            ]
            engine_name = getattr(correction_res, 'harness_engine_used', 'api')
            latency_val = getattr(correction_res, 'latency_ms', 0.0)
        else:
            _set_progress(req.talking_head_id, PipelineStage.LLM_CORRECTING, 70, "高精 ASR 直通与词库确定性匹配中...")
            candidate_subs = []
            for s in raw_segments:
                raw_t = str(s.get("raw_text") or s.get("text") or "")
                corr_t, _ = apply_glossary_corrections(raw_t)
                item = dict(s)
                item["raw_text"] = raw_t
                item["corrected_text"] = corr_t
                candidate_subs.append(item)
            summary_list = []
            engine_name = "direct_asr (glossary_deterministic)"
            latency_val = 0.0

        # 2.4 过滤纯语气填充词与无意义口癖占位符（如 '呃'、'额' 等独立碎词）及句首/句末停顿助词
        valid_clauses = asr_runner.filter_filler_segments(candidate_subs)
        valid_clauses = asr_runner.clean_filler_particles(valid_clauses)

        # 2.5 黄金自然句切分（单行优先，上限 15 字，彻底杜绝折行堆叠与连词挂尾腰斩）
        split_segments = asr_runner.split_into_readable_segments(valid_clauses, max_chars=15, soft_max=15, min_chunk=4)

        # 2.6 全局跨句碎片平滑合并（单行安全上限 15 字）
        corrected_segments = asr_runner.merge_short_segments(
            split_segments,
            min_chars=4,
            min_duration=1.0,
            max_chars=15,
            max_gap=0.55,
        )

        for idx, seg in enumerate(corrected_segments):
            if not seg.get("id") or seg["id"].startswith("seg_") or seg["id"].startswith("sub_"):
                seg["id"] = str(uuid.uuid4())

        th_duration = float(talking_head.duration or 0.0)
        if th_duration <= 0:
            th_duration = max((float(it.get("end_time", 0.0)) for it in corrected_segments), default=60.0)

        # 3.0 智能粗剪 (009): 自动识别口误重说、头尾动作与中段长静音压缩
        strat = EditingStrategy(video_speed=req.video_speed)
        prune_spans: List[PruneSpan] = []
        pruned_sub_ids: List[str] = []
        if strat.enable_auto_prune:
            from app.native_engine.prune_engine import auto_prune_engine
            prune_cfg = {
                "enable_head_prune": strat.enable_head_prune,
                "enable_tail_prune": strat.enable_tail_prune,
                "enable_retake_prune": strat.enable_retake_prune,
                "enable_mid_silence_prune": strat.enable_mid_silence_prune,
                "head_padding_seconds": strat.head_padding_seconds,
                "tail_padding_seconds": strat.tail_padding_seconds,
                "mid_silence_threshold": strat.mid_silence_threshold,
                "mid_silence_breath_gap": strat.mid_silence_breath_gap,
                "retake_pause_min": strat.retake_pause_min,
                "retake_similarity_min": strat.retake_similarity_min,
            }
            prune_spans, pruned_sub_ids = auto_prune_engine.analyze_and_prune(
                subtitles=corrected_segments,
                video_duration=th_duration,
                config=prune_cfg
            )

        from app.native_engine.prune_engine import auto_prune_engine
        active_prune_spans = [s for s in prune_spans if s.is_active]
        kept_spans = auto_prune_engine.compute_kept_spans(th_duration, active_prune_spans) if active_prune_spans else None
        effective_duration = round(sum(k.duration for k in kept_spans), 3) if kept_spans else th_duration

        # 3.2 紧凑重投影：提前生成以 0.0s 为起点的紧凑成片字幕列表（消除切点断裂与口误污染）
        if kept_spans:
            compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(corrected_segments, kept_spans)
        else:
            compact_subtitles = [dict(s) for s in corrected_segments if str(s.get("id")) not in pruned_sub_ids]

        # 3.5 AI 分镜决策（稀疏 Cue Sheet 契约 + 双层 60%~70% 黄金编排，基于紧凑时间轴）
        scene_decisions: Dict[str, SceneDecision] = {}
        scene_engine_note = "disabled"
        planned_windows: List[Dict[str, Any]] = []

        target_cov = req.strategy.broll_target_coverage if hasattr(req, "strategy") and req.strategy else 0.65

        from app.native_engine.scene_decision import (
            plan_dual_layer_broll,
            fallback_keyword_rules,
            validate_and_clip,
            BrollCueItem,
            generate_fallback_video_title
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
            for it in compact_subtitles
        ]

        cues_or_decisions = None
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
                        total_duration=effective_duration,
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
                        total_duration=effective_duration,
                        target_coverage=target_cov
                    )
                else:
                    planned_windows = plan_dual_layer_broll(
                        subtitles=decision_input,
                        cues=[],
                        total_duration=effective_duration,
                        target_coverage=target_cov
                    )
            except Exception as sd_err:
                # 真实执行铁律：AI 决策失败如实降级到关键词规则并在 pipeline_notes 标注，不假装成功
                scene_engine_note = f"keyword-rules (degraded: {str(sd_err)[:120]})"
                scene_decisions = fallback_keyword_rules(decision_input, total_duration=effective_duration, target_coverage=target_cov)
                raw_cues = [
                    BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
                    for s in decision_input if (sd := scene_decisions.get(s["id"])) and sd.broll_category
                ]
                planned_windows = plan_dual_layer_broll(
                    subtitles=decision_input,
                    cues=raw_cues,
                    total_duration=effective_duration,
                    target_coverage=target_cov
                )
        elif req.auto_broll:
            # 未开启大模型决策但开启自动空镜：直接走关键词规则 + 双层铺底
            scene_decisions = fallback_keyword_rules(decision_input, total_duration=effective_duration, target_coverage=target_cov)
            raw_cues = [
                BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
                for s in decision_input if (sd := scene_decisions.get(s["id"])) and sd.broll_category
            ]
            planned_windows = plan_dual_layer_broll(
                subtitles=decision_input,
                cues=raw_cues,
                total_duration=effective_duration,
                target_coverage=target_cov
            )

        # 智能命名与自主高光词：优先采用合并在分镜决策请求中的爆款标题与大模型高光词，无额外耗时
        ai_video_title = getattr(cues_or_decisions, "video_title", None) if cues_or_decisions else None
        if not ai_video_title:
            ai_video_title = generate_fallback_video_title(decision_input)

        ai_highlights_map = getattr(cues_or_decisions, "highlights", {}) if cues_or_decisions else {}

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

        # 实例化最终 broll 替换（支持相邻连切时切换不同素材，丰富画面层次）
        last_material_id = None
        last_end_time = -1.0
        for w in planned_windows:
            mats = cat_map.get(w["material_category"]) or []
            if not mats:
                continue
            is_continuous = (last_end_time > 0 and abs(w["start_time"] - last_end_time) <= 0.05)
            candidates = [m for m in mats if m.id != last_material_id] if (is_continuous and len(mats) > 1) else mats
            m = secrets.choice(candidates) if candidates else mats[0]
            last_material_id = m.id
            last_end_time = w["end_time"]
            brolls.append(BrollReplacement(
                start_time=w["start_time"],
                end_time=w["end_time"],
                material_id=m.id,
                material_category=w["material_category"]
            ))
        compact_sub_map = {str(cs.get("id")): cs for cs in compact_subtitles}

        for idx, item in enumerate(corrected_segments):
            c_text = item.get("corrected_text", "")
            sid = str(item.get("id") or f"sub_{idx}")

            is_p = sid in pruned_sub_ids
            p_reason = None
            p_span_id = None
            if is_p:
                for ps in prune_spans:
                    if ps.source_subtitle_id == sid:
                        p_reason = ps.reason
                        p_span_id = ps.id
                        break
                if not p_reason:
                    p_reason = PruneReason.RETAKE_DISCARD.value

            # 优先采用大模型自主上下文提取的高光词（自主地理常识与商业重点感知）
            ai_hws = ai_highlights_map.get(sid) or ai_highlights_map.get(str(idx)) or item.get("highlight_words")

            # 判定该字幕是否落在某个空镜窗口内（基于紧凑时间轴比对，已剔除的句子不分配空镜）
            assigned_broll_id = None
            assigned_cat = None
            assigned_dur = 0.0
            if not is_p and sid in compact_sub_map:
                c_sub = compact_sub_map[sid]
                mid_t = (float(c_sub["start_time"]) + float(c_sub["end_time"])) / 2.0
                for b in brolls:
                    if b.start_time <= mid_t <= b.end_time:
                        assigned_broll_id = b.material_id
                        assigned_cat = b.material_category
                        assigned_dur = round(b.end_time - b.start_time, 2)
                        break

            sd = scene_decisions.get(sid)
            if not sd and not is_p:
                sd = SceneDecision(
                    part="body",
                    broll_category=assigned_cat,
                    broll_duration=assigned_dur,
                    material_id=assigned_broll_id,
                    reason="双层黄金编排分镜" if assigned_cat else "保留口播真人画面"
                )
            elif assigned_broll_id and not is_p:
                sd.material_id = assigned_broll_id

            h_words = [
                HighlightWord(**w) for w in build_highlight_words(c_text, ai_hws)
                if isinstance(w, dict) and w.get("word")
            ] if not is_p else []

            subtitles.append(SubtitleSegment(
                id=sid,
                start_time=item["start_time"],
                end_time=item["end_time"],
                raw_text=item.get("raw_text", c_text),
                corrected_text=c_text,
                matched_category=assigned_cat if not is_p else None,
                matched_keywords=[w.word for w in h_words] if not is_p else [],
                highlight_words=h_words,
                words=item.get("words", []),
                scene_decision=sd if not is_p else None,
                broll_material_id=assigned_broll_id if not is_p else None,
                is_pruned=is_p,
                prune_reason=p_reason,
                prune_span_id=p_span_id
            ))

        # 预构建 compact_subtitles 对象列表存入 project
        p_compact_subs = []
        for cs in compact_subtitles:
            cs_id = str(cs.get("id"))
            matched_sub = next((s for s in subtitles if s.id == cs_id), None)
            p_compact_subs.append(SubtitleSegment(
                id=cs_id,
                start_time=float(cs["start_time"]),
                end_time=float(cs["end_time"]),
                raw_text=cs.get("raw_text", cs.get("corrected_text", "")),
                corrected_text=cs.get("corrected_text", ""),
                matched_category=matched_sub.matched_category if matched_sub else None,
                matched_keywords=matched_sub.matched_keywords if matched_sub else [],
                highlight_words=matched_sub.highlight_words if matched_sub else [],
                words=cs.get("words", []),
                scene_decision=matched_sub.scene_decision if matched_sub else None,
                broll_material_id=matched_sub.broll_material_id if matched_sub else None,
                is_pruned=False
            ))

        # 独立工程文件夹：每个待剪口播视频进入剪辑阶段自动安排专属目录 YYYYMMDD_HHMMSS_{title}
        task_dir_path = create_task_dir(Path(talking_head.filename).stem)
        task_dir_rel = str(task_dir_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/")

        # 策略初始化：将提炼的短视频标题同步为顶部胶囊主标题（截取核心关键词），替代默认占位符"科目二一把过秘籍"
        strat = EditingStrategy(video_speed=req.video_speed)
        clean_banner = re.sub(r"[·:：!！?？\s]+.*$", "", ai_video_title)[:10].strip()
        if clean_banner:
            strat.banner_main_title = clean_banner

        project = CutProject(
            title=ai_video_title,
            talking_head_id=talking_head.id,
            aspect_ratio=req.aspect_ratio,
            task_dir=task_dir_rel,
            strategy=strat,
            subtitles=subtitles,
            compact_subtitles=p_compact_subs,
            broll_replacements=brolls,
            prune_spans=prune_spans,
            raw_asr_segments=raw_segments,
            status=CutProjectStatus.DRAFT,
            corrections_summary=summary_list,
            pipeline_notes={"scene_decision_engine": scene_engine_note, "scene_decision_degraded": scene_engine_note.startswith("keyword-rules")},
            last_engine_used=engine_name,
            correction_latency_ms=latency_val
        )
        # 5. 智能剪辑成片压制与默认封面
        if req.auto_render:
            _set_progress(req.talking_head_id, PipelineStage.VIDEO_COMPOSING, 95, "正在压制生成成片预览与封面...")
            _set_progress(project.id, PipelineStage.VIDEO_COMPOSING, 95, "正在压制生成成片预览与封面...")

            dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"output_{project.id}_{project.aspect_ratio.replace(':', '_')}_{dt_str}.mp4"
            output_path = task_dir_path / output_filename

            from app.native_engine.prune_engine import auto_prune_engine
            active_prune_spans = [s for s in (project.prune_spans or []) if s.is_active]
            th_dur = float(talking_head.duration if talking_head.duration and talking_head.duration > 0 else 15.0)
            kept_spans = auto_prune_engine.compute_kept_spans(th_dur, active_prune_spans) if active_prune_spans else None

            # 1. 准备紧凑对齐的 ASS / SRT 字幕
            ass_path = task_dir_path / "subtitles.ass"
            speed = float(project.strategy.video_speed or 1.0)
            render_subtitles = _prepare_render_subtitles(project.subtitles, speed=speed, kept_spans=kept_spans)
            generate_ass_file(render_subtitles, ass_path, strategy=project.strategy.model_dump(), smooth_timings=True)
            srt_path = task_dir_path / "subtitles.srt"
            generate_srt_file(render_subtitles, srt_path, smooth_timings=True)

            broll_cuts_payload = []
            if project.strategy.broll_pacing != "talking_only":
                for b in project.broll_replacements:
                    m = storage_service.get_material(b.material_id)
                    if m:
                        full_b_path = STORAGE_DIR.parent / m.filepath
                        if full_b_path.exists():
                            b_st = b.start_time
                            b_et = b.end_time
                            eff_total_dur = sum(k.duration for k in kept_spans) if kept_spans else th_dur
                            if kept_spans and b_et > eff_total_dur + 0.1:
                                mapped = auto_prune_engine.map_interval_to_compact(b_st, b_et, kept_spans)
                                if not mapped:
                                    continue
                                b_st, b_et = mapped

                            transition_seconds = 0.0
                            for s in (project.compact_subtitles or project.subtitles):
                                if abs(s.start_time - b.start_time) <= 0.05 and s.scene_decision:
                                    transition_seconds = s.scene_decision.transition_seconds
                                    break
                            broll_cuts_payload.append({
                                "start_time": b_st,
                                "end_time": b_et,
                                "material_path": full_b_path,
                                "transition": transition_seconds
                            })

            full_th_path = STORAGE_DIR.parent / talking_head.filepath
            eff_total_dur = sum(k.duration for k in kept_spans) if kept_spans else th_dur
            try:
                compose_ok = composer.compose_jl_cut(
                    talking_head_path=full_th_path,
                    broll_cuts=broll_cuts_payload,
                    output_path=output_path,
                    aspect_ratio=project.aspect_ratio,
                    total_duration=eff_total_dur,
                    ass_subtitle_path=ass_path,
                    strategy=project.strategy.model_dump(),
                    kept_spans=kept_spans
                )
                if compose_ok and output_path.exists():
                    project.output_video_path = f"{project.task_dir}/{output_filename}"
                    project.output_absolute_path = str(output_path.resolve())
                    project.output_filename = output_filename
                    project.output_file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)
                    project.status = CutProjectStatus.COMPLETED

                    # 自动抽取 0.5s 默认封面帧（从已渲染成片提取）
                    cover_dest = task_dir_path / "cover.jpg"
                    if extract_cover_frame(output_path, cover_dest, timestamp=0.5):
                        project.cover_image_path = f"{project.task_dir}/cover.jpg"
                        project.cover_source = "frame"
            except Exception as compose_err:
                print(f"[analyze_and_cut] 自动生成预览成片跳过: {compose_err}")
                # 真实执行铁律：若真实素材 (>10KB) 合成发生致命异常则显式报错
                if full_th_path.exists() and full_th_path.stat().st_size > 10240:
                    raise HTTPException(status_code=500, detail=f"初剪成片合成失败: {str(compose_err)}")
        else:
            # 交互初剪极速模式：跳过耗时 5~8s 的全量 FFmpeg 压制，直接从口播原片抽取 0.5s 封面帧（<50ms）
            cover_dest = task_dir_path / "cover.jpg"
            if extract_cover_frame(full_th_path, cover_dest, timestamp=0.5):
                project.cover_image_path = f"{project.task_dir}/cover.jpg"
                project.cover_source = "frame"

        _save_task_manifest(task_dir_path, project)
        project_storage_service.save_project(project)
        _set_progress(project.id, PipelineStage.COMPLETED, 100, "智能初剪与纠偏已完成")
        _set_progress(req.talking_head_id, PipelineStage.COMPLETED, 100, "智能初剪与纠偏已完成")
        return _enrich_project_export_meta(project)
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
    target_coverage: float = 0.65  # 目标覆盖率 0.40~0.70 (黄金值 0.65)

@router.post("/{project_id}/scene-decision")
async def redecide_scenes(project_id: str, req: SceneDecisionRequest = SceneDecisionRequest()):
    """对既有工程单独重跑 AI 分镜决策（不重跑 ASR 与文本纠偏）；采用双层 60%~70% 黄金编排引擎（紧凑时间轴）"""
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    from app.native_engine.prune_engine import auto_prune_engine
    active_spans = [s for s in (p.prune_spans or []) if s.is_active]
    th = storage_service.get_material(p.talking_head_id)
    th_dur = float(th.duration if th and th.duration else 15.0)
    kept_spans = auto_prune_engine.compute_kept_spans(th_dur, active_spans) if active_spans else None
    effective_duration = round(sum(k.duration for k in kept_spans), 3) if kept_spans else th_dur

    if kept_spans:
        compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept_spans)
    else:
        compact_subtitles = [s for s in p.subtitles if not s.is_pruned]

    decision_input = [
        {
            "id": s.id if hasattr(s, "id") else s.get("id"),
            "text": (s.corrected_text or s.raw_text) if hasattr(s, "corrected_text") else (s.get("corrected_text") or s.get("raw_text")),
            "corrected_text": (s.corrected_text or s.raw_text) if hasattr(s, "corrected_text") else (s.get("corrected_text") or s.get("raw_text")),
            "start_time": s.start_time if hasattr(s, "start_time") else s.get("start_time"),
            "end_time": s.end_time if hasattr(s, "end_time") else s.get("end_time"),
            "words": [w.model_dump() if hasattr(w, "model_dump") else w for w in s.words] if (hasattr(s, "words") and s.words) or (isinstance(s, dict) and s.get("words")) else []
        }
        for s in compact_subtitles
        if not req.subtitle_ids or (s.id if hasattr(s, "id") else s.get("id")) in req.subtitle_ids
    ]
    if not decision_input:
        raise HTTPException(status_code=400, detail="没有匹配的有效字幕句")

    target_cov = req.target_coverage or (p.strategy.broll_target_coverage if hasattr(p.strategy, "broll_target_coverage") and p.strategy.broll_target_coverage else 0.65)
    total_duration = effective_duration

    from app.native_engine.scene_decision import (
        plan_dual_layer_broll,
        fallback_keyword_rules,
        validate_and_clip,
        BrollCueItem
    )

    planned_windows: List[Dict[str, Any]] = []
    engine_used = "minimax-cue"
    latency = 0.0
    degraded = False

    try:
        cues_or_decisions, engine_used, latency, ok = await get_active_harness().decide_scenes(decision_input)
        if not ok:
            raise RuntimeError(engine_used)

        if cues_or_decisions and isinstance(cues_or_decisions[0], BrollCueItem):
            planned_windows = plan_dual_layer_broll(
                subtitles=decision_input,
                cues=cues_or_decisions,
                total_duration=total_duration,
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
                total_duration=total_duration,
                target_coverage=target_cov
            )
        else:
            planned_windows = plan_dual_layer_broll(
                subtitles=decision_input,
                cues=[],
                total_duration=total_duration,
                target_coverage=target_cov
            )
    except Exception as e:
        engine_used = f"keyword-rules (degraded: {str(e)[:120]})"
        scene_decisions = fallback_keyword_rules(decision_input, total_duration=total_duration, target_coverage=target_cov)
        raw_cues = [
            BrollCueItem(start_time=float(s["start_time"]), end_time=float(s["start_time"]) + sd.broll_duration, category=sd.broll_category)
            for s in decision_input if (sd := scene_decisions.get(s["id"])) and sd.broll_category
        ]
        planned_windows = plan_dual_layer_broll(
            subtitles=decision_input,
            cues=raw_cues,
            total_duration=total_duration,
            target_coverage=target_cov
        )
        degraded = True
        latency = 0.0

    # 预加载空镜素材库
    venue_materials = storage_service.list_materials(MaterialCategory.VENUE)
    experience_materials = storage_service.list_materials(MaterialCategory.EXPERIENCE)
    lesson_materials = storage_service.list_materials(MaterialCategory.LESSON)

    cat_map = {
        MaterialCategory.VENUE: venue_materials,
        MaterialCategory.EXPERIENCE: experience_materials,
        MaterialCategory.LESSON: lesson_materials
    }

    new_brolls: List[BrollReplacement] = []
    last_material_id = None
    last_end_time = -1.0
    for w in planned_windows:
        mats = cat_map.get(w["material_category"]) or []
        if not mats:
            continue
        is_continuous = (last_end_time > 0 and abs(w["start_time"] - last_end_time) <= 0.05)
        candidates = [m for m in mats if m.id != last_material_id] if (is_continuous and len(mats) > 1) else mats
        m = secrets.choice(candidates) if candidates else mats[0]
        last_material_id = m.id
        last_end_time = w["end_time"]
        new_brolls.append(BrollReplacement(
            start_time=w["start_time"],
            end_time=w["end_time"],
            material_id=m.id,
            material_category=w["material_category"]
        ))

    # 字幕关联与更新（基于紧凑时间轴判定）
    compact_sub_map = {
        (cs.id if hasattr(cs, "id") else str(cs.get("id"))): cs
        for cs in compact_subtitles
    }
    from app.native_engine.keyword_matcher import match_keywords_in_segment
    for s in p.subtitles:
        c_text = s.corrected_text or s.raw_text
        kw_info = match_keywords_in_segment(c_text)
        matched_cat_str = kw_info.get("matched_category")
        s.matched_category = MaterialCategory(matched_cat_str) if matched_cat_str else None
        s.matched_keywords = kw_info.get("matched_keywords", [])

        assigned_broll_id = None
        assigned_cat = None
        assigned_dur = 0.0
        if not s.is_pruned and s.id in compact_sub_map:
            cs = compact_sub_map[s.id]
            cs_st = float(cs.start_time if hasattr(cs, "start_time") else cs.get("start_time", 0.0))
            cs_et = float(cs.end_time if hasattr(cs, "end_time") else cs.get("end_time", 0.0))
            mid = (cs_st + cs_et) / 2.0
            for b in new_brolls:
                if b.start_time <= mid <= b.end_time:
                    assigned_broll_id = b.material_id
                    assigned_cat = b.material_category
                    assigned_dur = round(b.end_time - b.start_time, 2)
                    break

        s.scene_decision = SceneDecision(
            part="body",
            broll_category=assigned_cat,
            broll_duration=assigned_dur,
            material_id=assigned_broll_id,
            reason="双层黄金编排分镜" if assigned_cat else "保留口播真人画面"
        )
        s.broll_material_id = assigned_broll_id

    p.broll_replacements = new_brolls
    p.compact_subtitles = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept_spans) if kept_spans else [s for s in p.subtitles if not s.is_pruned]
    p.pipeline_notes = {**(p.pipeline_notes or {}), "scene_decision_engine": engine_used, "scene_decision_degraded": degraded}
    project_storage_service.save_project(p)

    return {
        "code": 0,
        "message": "AI 分镜已重新编排完成",
        "data": {
            "project": _enrich_project_export_meta(p),
            "subtitles": [s.model_dump() for s in p.subtitles],
            "broll_replacements": [b.model_dump() for b in p.broll_replacements],
            "engine_used": engine_used,
            "latency_ms": round(latency, 1),
            "degraded": degraded
        }
    }

@router.get("/filter-presets")
async def get_filter_presets():
    """获取所有官方口播画质调优预设列表及说明"""
    presets = [
        {
            "id": "clean_natural",
            "name": "自然通透",
            "description": "面部暗沉驱散，皮肤质感自然白皙，发丝与眼神光清晰，适合日常手机口播",
            "is_recommended": True,
            "tags": ["日常口播", "提亮去黄", "眼神光增强"]
        },
        {
            "id": "crisp_hd",
            "name": "质感超清",
            "description": "边缘轮廓极其立体硬朗，抗二次压缩能力最强，适合商单讲解与高质感需求",
            "is_recommended": False,
            "tags": ["商业课程", "极锐质感", "抗二次压缩"]
        },
        {
            "id": "warm_radiant",
            "name": "元气暖肤",
            "description": "微升色温，面颊红润通透，改善苍白疲惫或冷光灯泛青泛灰",
            "is_recommended": False,
            "tags": ["美妆情感", "红润好气色", "柔化疲惫"]
        },
        {
            "id": "original",
            "name": "原始原色",
            "description": "保持素材原始色彩，不施加额外调色与锐化处理",
            "is_recommended": False,
            "tags": ["原片直出", "无滤镜", "已布光素材"]
        }
    ]
    return {
        "code": 0,
        "data": presets
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
    if p.task_dir:
        td = (STORAGE_DIR.parent / p.task_dir).resolve()
        if td.exists():
            _save_task_manifest(td, p)
    return _enrich_project_export_meta(p)

@router.put("/{project_id}/strategy", response_model=CutProject)
async def update_strategy(project_id: str, strategy: EditingStrategy):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    prune_fields = [
        'enable_auto_prune', 'enable_head_prune', 'enable_tail_prune', 'enable_retake_prune',
        'enable_mid_silence_prune', 'head_padding_seconds', 'tail_padding_seconds',
        'mid_silence_threshold', 'mid_silence_breath_gap', 'retake_pause_min', 'retake_similarity_min'
    ]
    prune_changed = any(getattr(p.strategy, f, None) != getattr(strategy, f, None) for f in prune_fields)
    p.strategy = strategy
    _sync_prune_spans(p, force=prune_changed)
    project_storage_service.save_project(p)
    if p.task_dir:
        td = (STORAGE_DIR.parent / p.task_dir).resolve()
        if td.exists():
            _save_task_manifest(td, p)
    return _enrich_project_export_meta(p)

class TogglePruneRequest(BaseModel):
    is_pruned: Optional[bool] = None

@router.post("/{project_id}/subtitles/{subtitle_id}/toggle-prune")
@router.post("/projects/{project_id}/subtitles/{subtitle_id}/toggle-prune")
async def toggle_subtitle_prune(project_id: str, subtitle_id: str, req: Optional[TogglePruneRequest] = None):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    target_sub = next((s for s in p.subtitles if s.id == subtitle_id), None)
    if not target_sub:
        raise HTTPException(status_code=404, detail="字幕片段不存在")

    target_is_pruned = req.is_pruned if (req and req.is_pruned is not None) else not target_sub.is_pruned
    target_sub.is_pruned = target_is_pruned

    from app.native_engine.prune_engine import auto_prune_engine
    if target_is_pruned:
        if not target_sub.prune_reason:
            target_sub.prune_reason = PruneReason.MANUAL.value
        found = False
        for s in p.prune_spans:
            if s.source_subtitle_id == target_sub.id or (target_sub.prune_span_id and s.id == target_sub.prune_span_id):
                s.is_active = True
                target_sub.prune_span_id = s.id
                found = True
                break
        if not found:
            span_id = str(uuid.uuid4())
            new_span = PruneSpan(
                id=span_id,
                start_time=round(float(target_sub.start_time), 3),
                end_time=round(float(target_sub.end_time), 3),
                reason=target_sub.prune_reason or PruneReason.MANUAL.value,
                source_subtitle_id=target_sub.id,
                duration=round(float(target_sub.end_time) - float(target_sub.start_time), 3),
                is_active=True
            )
            p.prune_spans.append(new_span)
            target_sub.prune_span_id = span_id
    else:
        for s in p.prune_spans:
            if s.source_subtitle_id == target_sub.id or (target_sub.prune_span_id and s.id == target_sub.prune_span_id):
                s.is_active = False

    th = storage_service.get_material(p.talking_head_id)
    th_dur = float(th.duration if th and th.duration else 15.0)
    active_spans = [s for s in p.prune_spans if s.is_active]
    kept = auto_prune_engine.compute_kept_spans(th_dur, active_spans)
    total_effective_duration = round(sum(k.duration for k in kept), 3)

    project_storage_service.save_project(p)
    compact_subs = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept)
    return {
        "success": True,
        "subtitle_id": subtitle_id,
        "is_pruned": target_sub.is_pruned,
        "prune_spans": [s.model_dump() for s in p.prune_spans],
        "total_effective_duration": total_effective_duration,
        "compact_subtitles": [s.model_dump() if hasattr(s, "model_dump") else s for s in compact_subs]
    }

class PruneConfigRequest(BaseModel):
    enable_head_prune: Optional[bool] = None
    enable_tail_prune: Optional[bool] = None
    enable_retake_prune: Optional[bool] = None
    enable_mid_silence_prune: Optional[bool] = None
    head_padding_seconds: Optional[float] = None
    tail_padding_seconds: Optional[float] = None
    mid_silence_threshold: Optional[float] = None
    mid_silence_breath_gap: Optional[float] = None
    retake_pause_min: Optional[float] = None
    retake_similarity_min: Optional[float] = None

@router.post("/{project_id}/prune-config")
@router.post("/projects/{project_id}/prune-config")
async def update_prune_config(project_id: str, req: PruneConfigRequest):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    strat = p.strategy
    if req.enable_head_prune is not None:
        strat.enable_head_prune = req.enable_head_prune
    if req.enable_tail_prune is not None:
        strat.enable_tail_prune = req.enable_tail_prune
    if req.enable_retake_prune is not None:
        strat.enable_retake_prune = req.enable_retake_prune
    if req.enable_mid_silence_prune is not None:
        strat.enable_mid_silence_prune = req.enable_mid_silence_prune
    if req.head_padding_seconds is not None:
        strat.head_padding_seconds = req.head_padding_seconds
    if req.tail_padding_seconds is not None:
        strat.tail_padding_seconds = req.tail_padding_seconds
    if req.mid_silence_threshold is not None:
        strat.mid_silence_threshold = req.mid_silence_threshold
    if req.mid_silence_breath_gap is not None:
        strat.mid_silence_breath_gap = req.mid_silence_breath_gap
    if req.retake_pause_min is not None:
        strat.retake_pause_min = req.retake_pause_min
    if req.retake_similarity_min is not None:
        strat.retake_similarity_min = req.retake_similarity_min

    th = storage_service.get_material(p.talking_head_id)
    th_dur = float(th.duration if th and th.duration else 15.0)

    from app.native_engine.prune_engine import auto_prune_engine
    prune_cfg = {
        "enable_head_prune": strat.enable_head_prune,
        "enable_tail_prune": strat.enable_tail_prune,
        "enable_retake_prune": strat.enable_retake_prune,
        "enable_mid_silence_prune": strat.enable_mid_silence_prune,
        "head_padding_seconds": strat.head_padding_seconds,
        "tail_padding_seconds": strat.tail_padding_seconds,
        "mid_silence_threshold": strat.mid_silence_threshold,
        "mid_silence_breath_gap": strat.mid_silence_breath_gap,
        "retake_pause_min": strat.retake_pause_min,
        "retake_similarity_min": strat.retake_similarity_min,
    }
    new_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=p.subtitles,
        video_duration=th_dur,
        config=prune_cfg
    )

    manual_spans = [s for s in p.prune_spans if s.reason == PruneReason.MANUAL.value and s.is_active]
    manual_sub_ids = {s.source_subtitle_id for s in manual_spans if s.source_subtitle_id}

    p.prune_spans = new_spans + [s for s in manual_spans if not any(ns.id == s.id for ns in new_spans)]

    for sub in p.subtitles:
        if sub.id in manual_sub_ids:
            sub.is_pruned = True
            sub.prune_reason = PruneReason.MANUAL.value
        elif sub.id in pruned_ids:
            sub.is_pruned = True
            sub.prune_reason = PruneReason.RETAKE_DISCARD.value
        else:
            sub.is_pruned = False
            sub.prune_reason = None

    project_storage_service.save_project(p)
    total_pruned_seconds = round(sum(s.duration for s in p.prune_spans if s.is_active), 3)
    active_spans = [s for s in p.prune_spans if s.is_active]
    kept = auto_prune_engine.compute_kept_spans(th_dur, active_spans)
    compact_subs = auto_prune_engine.reproject_subtitles_to_compact(p.subtitles, kept)

    return {
        "success": True,
        "total_pruned_seconds": total_pruned_seconds,
        "prune_spans": [s.model_dump() for s in p.prune_spans],
        "compact_subtitles": [s.model_dump() if hasattr(s, "model_dump") else s for s in compact_subs]
    }

@router.post("/{project_id}/render", response_model=CutProject)
async def render_project(
    project_id: str,
    video_speed: Optional[float] = Query(None, description="自定义导出倍速 (支持任意浮点数，如 1.08, 1.12, 1.15)")
):
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    th = storage_service.get_material(p.talking_head_id)
    if not th:
        raise HTTPException(status_code=404, detail="口播素材不存在")

    if video_speed is not None and not isinstance(video_speed, type(Query(None))):
        p.strategy.video_speed = max(0.5, min(3.0, round(float(video_speed), 2)))

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

    dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"output_{p.id}_{p.aspect_ratio.replace(':', '_')}_{dt_str}.mp4"
    output_path = target_task_dir / output_filename

    # 1. 确保粗剪区间与策略同步，并计算有效保留时间区间 (KeptSpans)
    from app.native_engine.prune_engine import auto_prune_engine
    changed = _sync_prune_spans(p, force=False)
    if changed:
        project_storage_service.save_project(p)

    active_prune_spans = [s for s in (p.prune_spans or []) if s.is_active]
    th_dur = float(th.duration if th.duration > 0 else 15.0)
    kept_spans = auto_prune_engine.compute_kept_spans(th_dur, active_prune_spans) if active_prune_spans else None

    # 2. 如果用户策略设为纯口播 (talking_only)，清空参与渲染的空镜
    broll_cuts_payload = []
    if p.strategy.broll_pacing != "talking_only":
        for b in p.broll_replacements:
            m = storage_service.get_material(b.material_id)
            if m:
                full_b_path = STORAGE_DIR.parent / m.filepath
                if full_b_path.exists():
                    b_st = b.start_time
                    b_et = b.end_time
                    eff_total_dur = sum(k.duration for k in kept_spans) if kept_spans else th_dur
                    if kept_spans and b_et > eff_total_dur + 0.1:
                        mapped = auto_prune_engine.map_interval_to_compact(b_st, b_et, kept_spans)
                        if not mapped:
                            continue
                        b_st, b_et = mapped

                    # 附带该窗口对应字幕的分镜转场时长（fade 档由合成器消费）
                    transition_seconds = 0.0
                    for s in (p.compact_subtitles or p.subtitles):
                        if abs(s.start_time - b.start_time) <= 0.05 and s.scene_decision:
                            transition_seconds = s.scene_decision.transition_seconds
                            break
                    broll_cuts_payload.append({
                        "start_time": b_st,
                        "end_time": b_et,
                        "material_path": full_b_path,
                        "transition": transition_seconds
                    })

    # 3. 生成 ASS 高级高亮字幕文件与 SRT 文件至专属任务目录（重投影至紧凑时间轴）
    ass_path = target_task_dir / "subtitles.ass"
    speed = float(p.strategy.video_speed or 1.0)
    render_subtitles = _prepare_render_subtitles(p.subtitles, speed=speed, kept_spans=kept_spans)
    generate_ass_file(
        render_subtitles,
        ass_path,
        strategy=p.strategy.model_dump(),
        smooth_timings=True,
    )

    srt_path = target_task_dir / "subtitles.srt"
    generate_srt_file(render_subtitles, srt_path, smooth_timings=True)

    # 4. 复合渲染：空镜平替 + ASS字幕 + 顶部横幅 + 水印
    full_th_path = STORAGE_DIR.parent / th.filepath
    eff_total_dur = sum(k.duration for k in kept_spans) if kept_spans else th_dur
    try:
        success = composer.compose_jl_cut(
            talking_head_path=full_th_path,
            broll_cuts=broll_cuts_payload,
            output_path=output_path,
            aspect_ratio=p.aspect_ratio,
            total_duration=eff_total_dur,
            ass_subtitle_path=ass_path,
            strategy=p.strategy.model_dump(),
            kept_spans=kept_spans
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

        # 自动抽取 0.5s 默认封面帧（从成片抽取），便于在成片网格中直接显示缩略图
        cover_dest = target_task_dir / "cover.jpg"
        if extract_cover_frame(output_path, cover_dest, timestamp=0.5):
            p.cover_image_path = f"{p.task_dir}/cover.jpg"
            p.cover_source = "frame"

        # 安全清理上一版渲染产物，防止磁盘膨胀，若被播放器占用则静默忽略
        for old_f in target_task_dir.glob("output_*.mp4"):
            if old_f.name != output_filename:
                try:
                    old_f.unlink(missing_ok=True)
                except Exception as e:
                    print(f"[render] 保留旧渲染文件 (可能正在被占用): {e}")

        if old_output_path and old_output_path.exists() and old_output_path != output_path.resolve():
            try:
                old_output_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"[render] 保留旧渲染文件 (可能正在被播放): {e}")

        _save_task_manifest(target_task_dir, p)
    else:
        p.status = CutProjectStatus.FAILED

    project_storage_service.save_project(p)
    return _enrich_project_export_meta(p)

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
    if p.task_dir:
        target_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
        _save_task_manifest(target_dir, p)

    return {
        "code": 0,
        "data": {
            "cover_image_path": p.cover_image_path,
            "cover_source": p.cover_source,
            "cover_url": f"/{p.cover_image_path}"
        }
    }

@router.post("/{project_id}/cover/upload")
async def upload_project_cover(
    project_id: str,
    file: UploadFile = File(...)
):
    """用户直接上传本地图片作为工程封面"""
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    ext = Path(file.filename or "").suffix.lower()
    content_type = file.content_type or ""
    if not (content_type.startswith("image/") or ext in valid_exts):
        raise HTTPException(status_code=400, detail="请上传图片格式文件 (jpg, png, webp 等)")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 10MB 上限")

    cover_ext = ext if ext in valid_exts else ".jpg"
    if p.task_dir:
        target_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        cover_name = f"cover{cover_ext}"
        cover_path = target_dir / cover_name
        rel_cover = f"{p.task_dir}/{cover_name}"
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        cover_name = f"cover_{p.id}_{ts}{cover_ext}"
        cover_path = COVERS_DIR / cover_name
        rel_cover = f"storage/covers/{cover_name}"

    cover_path.write_bytes(content)
    p.cover_image_path = rel_cover
    p.cover_source = "upload"
    project_storage_service.save_project(p)

    if p.task_dir:
        target_dir = (STORAGE_DIR.parent / p.task_dir).resolve()
        _save_task_manifest(target_dir, p)

    return {
        "code": 0,
        "message": "封面上传成功",
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

def _cleanup_project_files(p: CutProject):
    """安全清理工程关联的磁盘生成文件及专属任务目录"""
    # 1. 清理专属任务目录（包含 output_*.mp4, cover.jpg, subtitles.ass, project_manifest.json 等）
    if p.task_dir:
        try:
            td = (STORAGE_DIR.parent / p.task_dir).resolve()
            if td.exists() and td.is_dir() and TASKS_DIR.resolve() in td.parents:
                shutil.rmtree(td, ignore_errors=True)
        except Exception as e:
            print(f"[_cleanup_project_files] 清理任务目录失败 {p.task_dir}: {e}")

    # 2. 如果 output_video_path 位于历史 outputs 目录下，单独清理
    if p.output_video_path:
        try:
            vp = (STORAGE_DIR.parent / p.output_video_path).resolve()
            if vp.exists() and vp.is_file() and (OUTPUTS_DIR.resolve() in vp.parents or TASKS_DIR.resolve() in vp.parents):
                vp.unlink(missing_ok=True)
        except Exception as e:
            print(f"[_cleanup_project_files] 清理成片视频文件失败 {p.output_video_path}: {e}")

    # 3. 如果 cover 位于历史 covers 目录下，单独清理
    if p.cover_image_path:
        try:
            cp = (STORAGE_DIR.parent / p.cover_image_path).resolve()
            if cp.exists() and cp.is_file() and COVERS_DIR.resolve() in cp.parents:
                cp.unlink(missing_ok=True)
        except Exception as e:
            print(f"[_cleanup_project_files] 清理封面文件失败 {p.cover_image_path}: {e}")

class BatchDeleteProjectsRequest(BaseModel):
    project_ids: List[str]
    delete_files: bool = True

@router.post("/batch-delete")
async def batch_delete_projects(req: BatchDeleteProjectsRequest):
    """批量删除剪辑工程，并根据需求清理生成的视频与专属任务目录"""
    deleted_ids: List[str] = []
    for pid in req.project_ids:
        p = project_storage_service.get_by_project_id(pid)
        if not p:
            continue
        if req.delete_files:
            _cleanup_project_files(p)
        if project_storage_service.delete_project(pid):
            deleted_ids.append(pid)
    return {
        "code": 0,
        "message": f"成功删除 {len(deleted_ids)} 个工程",
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids
    }

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    delete_files: bool = Query(True, description="是否同步清理本地任务目录与生成视频")
):
    """根据工程 ID 删除工程记录及关联生成文件"""
    p = project_storage_service.get_by_project_id(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="工程不存在")

    if delete_files:
        _cleanup_project_files(p)

    success = project_storage_service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除工程失败")

    return {
        "code": 0,
        "message": "工程及关联文件已成功删除",
        "project_id": project_id
    }


