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


class BatchSubmitRequest(BaseModel):
    material_ids: List[str]
    aspect_ratio: str = "9:16"
    concurrency: Optional[int] = None  # 用户可指定并发；缺省用硬件推荐值，硬顶 8


def _persist(job: BatchJob) -> None:
    BatchJobRepository().save(job)


async def _run_one(job: BatchJob, item: BatchJobItem, aspect_ratio: str) -> None:
    """执行单个口播视频的完整剪辑流水线，任何失败如实落库"""
    from app.api.editor import AnalyzeAndCutRequest, analyze_and_cut, render_project, redecide_scenes, SceneDecisionRequest

    item.status = "running"
    item.progress = 5
    _persist(job)
    try:
        project = await analyze_and_cut(AnalyzeAndCutRequest(
            talking_head_id=item.material_id,
            aspect_ratio=aspect_ratio,
            auto_broll=True,
            force_retranscribe=False,
            enable_scene_decision=True
        ))
        item.project_id = project.id
        item.progress = 70
        _persist(job)

        # AI 分镜决策：跨场地/体检/教学场景重排空镜窗口（内部失败自动降级关键词规则并记录引擎）
        try:
            await redecide_scenes(project.id, SceneDecisionRequest())
        except Exception as se:
            print(f"[Batch] 分镜决策异常(渲染继续, 关键词规则兜底): {str(se)[:160]}")
        item.progress = 85
        _persist(job)

        await render_project(project.id)
        item.status = "completed"
        item.progress = 100
    except Exception as e:
        detail = getattr(e, "detail", None) or str(e)
        item.status = "failed"
        item.error = f"批量剪辑失败: {detail}"
    finally:
        if item.status in ("completed", "failed"):
            job.completed_count = sum(1 for i in job.items if i.status in ("completed", "failed"))
        _persist(job)


async def _execute_job(job_id: str, aspect_ratio: str) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = BatchJobStatus.RUNNING
    _persist(job)
    sem = asyncio.Semaphore(max(1, job.concurrency))

    async def worker(item: BatchJobItem):
        async with sem:
            await _run_one(job, item, aspect_ratio)

    try:
        await asyncio.gather(*(worker(i) for i in job.items))
    finally:
        job.status = BatchJobStatus.FINISHED
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
        items.append(BatchJobItem(material_id=mid))

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
    bg_tasks.add_task(_execute_job, job.id, req.aspect_ratio)

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
    concurrency: Optional[int] = Form(None)
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
        items.append(BatchJobItem(material_id=material.id))

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

    bg_tasks.add_task(_execute_job, job.id, aspect_ratio)

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
        items.append(BatchJobItem(material_id=material.id))

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

    bg_tasks.add_task(_execute_job, job.id, req.aspect_ratio)

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
        items_out.append(d)

    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "concurrency": job.concurrency,
            "completed_count": job.completed_count,
            "items": items_out
        }
    }


@router.get("/jobs")
async def list_batch_jobs():
    jobs = list(_jobs.values()) or BatchJobRepository().list_all()
    return {
        "code": 0,
        "data": [
            {
                "job_id": j.id,
                "status": j.status.value if hasattr(j.status, "value") else str(j.status),
                "total_count": j.total_count,
                "completed_count": j.completed_count,
                "concurrency": j.concurrency,
                "created_at": getattr(j, "created_at", None)
            }
            for j in jobs
        ]
    }
