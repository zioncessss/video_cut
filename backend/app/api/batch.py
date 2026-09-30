"""批量智能剪辑：多口播视频真实流水线（ASR→纠偏→高亮→分镜决策→合成）。

每个视频独立执行与记录：单项失败落真实错误详情不中断其余（真实执行铁律）；
并发数取硬件推荐槽位（constitution IV）；任务持久化 batch_jobs 表，重启后可查询最终态。
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional

from app.models.entities import (
    BatchJob,
    BatchJobItem,
    BatchJobStatus,
    MaterialCategory,
)
from app.core.resource import get_hardware_metrics
from app.db.repository import BatchJobRepository
from app.native_engine.storage import storage_service

router = APIRouter()

# 内存态作业表（与 batch_jobs 表同步持久化；重启后仅可查询最终态，不恢复执行）
_jobs: dict = {}
# 运行中的任务调度 Task 映射表: {job_id: {material_id: asyncio.Task}}
_running_tasks: dict = {}


class BatchSubmitRequest(BaseModel):
    material_ids: List[str]
    aspect_ratio: str = "9:16"
    concurrency: Optional[int] = None  # 用户可指定并发；缺省用硬件推荐值，硬顶 8
    video_speed: float = 1.0
    filter_banned_words: bool = False


def _persist(job: BatchJob) -> None:
    BatchJobRepository().save(job)


def _count_states(job: BatchJob) -> tuple:
    """以 items 实时结算成功/失败数（历史批次落库的 completed_count 曾混入失败项，
    统一重算保证新旧数据展示一致；items 为空时退回落库值）"""
    if job.items:
        completed = sum(1 for i in job.items if i.status == "completed")
        failed = sum(1 for i in job.items if i.status == "failed")
        return completed, failed
    return job.completed_count, 0


async def _run_one(
    job: BatchJob,
    item: BatchJobItem,
    aspect_ratio: str,
    video_speed: float = 1.0,
    filter_banned_words: bool = False
) -> None:
    """执行单个口播视频的完整剪辑流水线，任何失败如实落库"""
    from app.api.editor import AnalyzeAndCutRequest, analyze_and_cut, render_project, redecide_scenes, SceneDecisionRequest

    item.status = "running"
    item.progress = 5
    _persist(job)
    await asyncio.sleep(0.05)
    try:
        project = await analyze_and_cut(AnalyzeAndCutRequest(
            talking_head_id=item.material_id,
            aspect_ratio=aspect_ratio,
            auto_broll=True,
            force_retranscribe=False,
            enable_scene_decision=True,
            video_speed=video_speed,
            auto_render=False
        ))
        item.project_id = project.id
        item.progress = 60
        _persist(job)
        await asyncio.sleep(0.05)

        # 批量流水线直接进行全量成片压制，保证生成可直接播放、导出的最终 MP4 与封面
        if filter_banned_words or video_speed != 1.0:
            await render_project(project.id, video_speed=video_speed, filter_banned_words=filter_banned_words)
        else:
            await render_project(project.id)
        item.status = "completed"
        item.progress = 100
        await asyncio.sleep(0.05)
    except Exception as e:
        detail = getattr(e, "detail", None) or str(e)
        item.status = "failed"
        item.error = f"批量剪辑失败: {detail}"
    finally:
        if item.status in ("completed", "failed"):
            # completed_count 只统计真实成功项，失败项计入 failed_count；
            # 混用会把“已完成 5/5”顶在失败批次上，误导用户以为全部成功
            job.completed_count = sum(1 for i in job.items if i.status == "completed")
        _persist(job)


async def _execute_job(
    job_id: str,
    aspect_ratio: str,
    video_speed: float = 1.0,
    retry_failed_only: bool = False,
    filter_banned_words: bool = False
) -> None:
    job = _jobs.get(job_id) or BatchJobRepository().get_by_id(job_id)
    if not job:
        return
    _jobs[job_id] = job
    job.status = BatchJobStatus.RUNNING
    _persist(job)

    sem = asyncio.Semaphore(max(1, job.concurrency))
    job_tasks = {}
    _running_tasks[job_id] = job_tasks

    async def worker(item: BatchJobItem, delay: float = 0.0):
        if delay > 0:
            await asyncio.sleep(delay)

        if job.status == BatchJobStatus.CANCELED:
            item.status = "canceled"
            item.error = "作业已被用户主动取消"
            _persist(job)
            return

        async with sem:
            if job.status == BatchJobStatus.CANCELED:
                item.status = "canceled"
                item.error = "作业已被用户主动取消"
                _persist(job)
                return
            try:
                eff_banned = getattr(item, "filter_banned_words", False) or filter_banned_words
                await _run_one(job, item, aspect_ratio, video_speed, filter_banned_words=eff_banned)
            except asyncio.CancelledError:
                item.status = "canceled"
                item.error = "任务被主动取消 (Cancelled)"
                _persist(job)
                raise

    target_items = [i for i in job.items if i.status in ("failed", "queued", "interrupted")] if retry_failed_only else job.items
    for it in target_items:
        it.status = "queued"
        it.error = None
        it.progress = 0
    _persist(job)

    tasks = []
    for idx, it in enumerate(target_items):
        t = asyncio.create_task(worker(it, delay=idx * 0.25))
        job_tasks[it.material_id] = t
        tasks.append(t)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        _running_tasks.pop(job_id, None)
        if job.status != BatchJobStatus.CANCELED:
            job.status = BatchJobStatus.FINISHED
        completed_count, _ = _count_states(job)
        job.completed_count = completed_count
        _persist(job)


@router.post("/submit")
async def submit_batch(req: BatchSubmitRequest, bg_tasks: BackgroundTasks):
    if not req.material_ids:
        raise HTTPException(status_code=400, detail="material_ids 不能为空")

    items: List[BatchJobItem] = []
    for mid in req.material_ids:
        material = storage_service.get_material(mid)
        if not material:
            raise HTTPException(status_code=404, detail=f"口播素材不存在: {mid}")
        if material.category != MaterialCategory.TALKING_HEAD:
            raise HTTPException(status_code=400, detail=f"素材 {material.filename} 不是口播分镜，无法批量剪辑")
        items.append(BatchJobItem(material_id=mid, filter_banned_words=req.filter_banned_words))

    metrics = get_hardware_metrics()
    # 并发：用户指定优先（1~8 硬顶），缺省用硬件推荐值
    concurrency = max(1, min(req.concurrency or metrics.recommended_concurrency, 8))
    job = BatchJob(
        total_count=len(items),
        completed_count=0,
        concurrency=concurrency,
        status=BatchJobStatus.QUEUED,
        items=items
    )
    _jobs[job.id] = job
    _persist(job)

    # 响应先返回 job_id，批处理在后台任务中真实执行
    bg_tasks.add_task(_execute_job, job.id, req.aspect_ratio, req.video_speed, filter_banned_words=req.filter_banned_words)

    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "queued": job.total_count,
            "concurrency": job.concurrency
        }
    }


@router.post("/upload-and-cut")
async def upload_and_cut(
    bg_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    aspect_ratio: str = Form("9:16"),
    concurrency: Optional[int] = Form(None),
    video_speed: float = Form(1.0),
    filter_banned_words: bool = Form(False)
):
    """批量直接上传口播视频并立即加入智能混剪队列"""
    if not files:
        raise HTTPException(status_code=400, detail="未上传任何口播视频文件")

    items: List[BatchJobItem] = []
    for f in files:
        content = await f.read()
        if len(content) == 0:
            continue
        material = storage_service.save_material(
            category=MaterialCategory.TALKING_HEAD,
            filename=f.filename or "talking_head.mp4",
            source_path_or_bytes=content
        )
        items.append(BatchJobItem(material_id=material.id, filter_banned_words=filter_banned_words))

    if not items:
        raise HTTPException(status_code=400, detail="上传的视频文件均为空文件")

    metrics = get_hardware_metrics()
    actual_concurrency = max(1, min(concurrency or metrics.recommended_concurrency, 8))
    job = BatchJob(
        total_count=len(items),
        completed_count=0,
        concurrency=actual_concurrency,
        status=BatchJobStatus.QUEUED,
        items=items
    )
    _jobs[job.id] = job
    _persist(job)

    bg_tasks.add_task(_execute_job, job.id, aspect_ratio, video_speed, filter_banned_words=filter_banned_words)

    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "queued": job.total_count,
            "concurrency": job.concurrency
        }
    }


class BatchImportRequest(BaseModel):
    file_paths: List[str]
    aspect_ratio: str = "9:16"
    concurrency: Optional[int] = None
    video_speed: float = 1.0
    filter_banned_words: bool = False


@router.post("/import-and-cut")
async def import_and_cut(req: BatchImportRequest, bg_tasks: BackgroundTasks):
    """Electron 桌面端零拷贝批量导入本地口播视频并开启混剪"""
    from pathlib import Path
    if not req.file_paths:
        raise HTTPException(status_code=400, detail="file_paths 列表不能为空")

    items: List[BatchJobItem] = []
    for fp in req.file_paths:
        p = Path(fp)
        if not p.exists() or not p.is_file():
            continue
        material = storage_service.save_material(
            category=MaterialCategory.TALKING_HEAD,
            filename=p.name,
            source_path_or_bytes=p
        )
        items.append(BatchJobItem(material_id=material.id, filter_banned_words=req.filter_banned_words))

    if not items:
        raise HTTPException(status_code=400, detail="指定的本地文件均不存在或无法访问")

    metrics = get_hardware_metrics()
    concurrency = max(1, min(req.concurrency or metrics.recommended_concurrency, 8))
    job = BatchJob(
        total_count=len(items),
        completed_count=0,
        concurrency=concurrency,
        status=BatchJobStatus.QUEUED,
        items=items
    )
    _jobs[job.id] = job
    _persist(job)

    bg_tasks.add_task(_execute_job, job.id, req.aspect_ratio, req.video_speed, filter_banned_words=req.filter_banned_words)

    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "queued": job.total_count,
            "concurrency": job.concurrency
        }
    }


@router.get("/jobs/{job_id}")
async def get_batch_job(job_id: str):
    job = _jobs.get(job_id) or BatchJobRepository().get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    # 逐条补全工程信息、成片路径、封面、任务独立目录：完成的条目直接给出可打开的输出文件（真实产物，绝不伪造）
    from app.core.config import STORAGE_DIR
    from app.native_engine.project_storage import project_storage_service
    items_out = []
    for i in job.items:
        d = i.model_dump()
        mat = storage_service.get_material(i.material_id)
        if mat:
            d["material_filename"] = mat.filename
            d["duration"] = mat.duration
        p = None
        if i.project_id:
            p = project_storage_service.get_by_project_id(i.project_id)
        if not p and i.material_id:
            p = project_storage_service.get_by_material_id(i.material_id)
            if p:
                d["project_id"] = p.id
        if p:
            d["project_title"] = p.title
            d["task_dir"] = p.task_dir
            d["cover_image_path"] = p.cover_image_path
            if p.output_video_path:
                d["output_video_path"] = p.output_video_path
                full_path = STORAGE_DIR.parent / p.output_video_path
                if full_path.exists():
                    d["output_absolute_path"] = str(full_path.resolve())
                    d["output_file_size_mb"] = round(full_path.stat().st_size / (1024 * 1024), 2)
        if i.status == "running":
            from app.api.editor import _pipeline_progress
            prog = _pipeline_progress.get(i.material_id) or (
                _pipeline_progress.get(i.project_id) if i.project_id else None
            )
            if prog and getattr(prog, "percent", 0) > d.get("progress", 0):
                d["progress"] = prog.percent
                d["stage_message"] = getattr(prog, "message", None)
        items_out.append(d)

    completed_count, failed_count = _count_states(job)
    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "concurrency": job.concurrency,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "items": items_out
        }
    }


@router.get("/jobs")
async def list_batch_jobs():
    db_jobs = BatchJobRepository().list_all()
    jobs_map = {j.id: j for j in db_jobs}
    # 内存活跃态优先覆盖，确保正在运行的任务状态最新且已落库历史不丢失
    for j in _jobs.values():
        jobs_map[j.id] = j
    jobs = sorted(jobs_map.values(), key=lambda x: getattr(x, "created_at", 0) or 0, reverse=True)
    return {
        "code": 0,
        "data": [
            {
                "job_id": j.id,
                "status": j.status.value if hasattr(j.status, "value") else str(j.status),
                "total_count": j.total_count,
                "completed_count": _count_states(j)[0],
                "failed_count": _count_states(j)[1],
                "concurrency": j.concurrency,
                "created_at": getattr(j, "created_at", None)
            }
            for j in jobs
        ]
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_batch_job(job_id: str):
    """主动终止取消指定的批量混剪作业"""
    job = _jobs.get(job_id) or BatchJobRepository().get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    canceled_count = 0
    if job.status in (BatchJobStatus.RUNNING, BatchJobStatus.QUEUED):
        job.status = BatchJobStatus.CANCELED

        job_tasks = _running_tasks.get(job_id, {})
        for mid, task in job_tasks.items():
            if not task.done():
                task.cancel()

        for it in job.items:
            if it.status in ("queued", "running"):
                it.status = "canceled"
                it.error = "作业已被用户主动取消"
                canceled_count += 1

        _persist(job)

    return {
        "code": 0,
        "message": "已成功取消批量剪辑作业",
        "job_id": job.id,
        "status": "canceled",
        "canceled_items_count": canceled_count
    }


@router.post("/jobs/{job_id}/retry-failed")
async def retry_failed_batch_job(job_id: str, bg_tasks: BackgroundTasks):
    """仅重新执行批处理作业中失败的条目"""
    job = _jobs.get(job_id) or BatchJobRepository().get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    target_items = [it for it in job.items if it.status in ("failed", "queued", "interrupted")]
    if not target_items:
        raise HTTPException(status_code=400, detail="该批次中没有失败条目，无需重试")

    if job.status == BatchJobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="当前批次正在运行中，请等待完成后再重试")

    # 重置待重试项状态为 queued
    for it in target_items:
        it.status = "queued"
        it.error = None
        it.progress = 0

    job.status = BatchJobStatus.QUEUED
    _jobs[job.id] = job
    _persist(job)

    # 尝试从已有工程中探测原始 aspect_ratio 和 video_speed，避免失败项重试时被重置为默认 9:16/1.0
    from app.native_engine.project_storage import project_storage_service
    detected_aspect_ratio = "9:16"
    detected_video_speed = 1.0
    for it in job.items:
        if it.project_id:
            proj = project_storage_service.get_by_project_id(it.project_id)
            if proj:
                detected_aspect_ratio = proj.aspect_ratio or detected_aspect_ratio
                if proj.strategy and proj.strategy.video_speed:
                    detected_video_speed = proj.strategy.video_speed
                break

    # 启动后台任务重跑失败/未完成项
    any_filter_banned = any(getattr(it, "filter_banned_words", False) for it in target_items)
    if any_filter_banned:
        bg_tasks.add_task(_execute_job, job.id, detected_aspect_ratio, detected_video_speed, retry_failed_only=True, filter_banned_words=True)
    else:
        bg_tasks.add_task(_execute_job, job.id, detected_aspect_ratio, detected_video_speed, retry_failed_only=True)

    return {
        "code": 0,
        "message": f"已将 {len(target_items)} 个未完成条目重新压入混剪队列",
        "job_id": job.id,
        "retrying_count": len(target_items)
    }

