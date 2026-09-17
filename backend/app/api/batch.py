"""批量智能剪辑：多口播视频真实流水线（ASR→纠偏→高亮→分镜决策→合成）。

每个视频独立执行与记录：单项失败落真实错误详情不中断其余（真实执行铁律）；
并发数取硬件推荐槽位（constitution IV）；任务持久化 batch_jobs 表，重启后可查询最终态。
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
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


def _persist(job: BatchJob) -> None:
    BatchJobRepository().save(job)


async def _run_one(job: BatchJob, item: BatchJobItem, aspect_ratio: str) -> None:
    """执行单个口播视频的完整剪辑流水线，任何失败如实落库"""
    from app.api.editor import AnalyzeAndCutRequest, analyze_and_cut, render_project

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
    job = BatchJob(
        total_count=len(items),
        completed_count=0,
        concurrency=max(1, metrics.recommended_concurrency),
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


@router.get("/jobs/{job_id}")
async def get_batch_job(job_id: str):
    job = _jobs.get(job_id) or BatchJobRepository().get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return {
        "code": 0,
        "data": {
            "job_id": job.id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "concurrency": job.concurrency,
            "completed_count": job.completed_count,
            "items": [i.model_dump() for i in job.items]
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
                "concurrency": j.concurrency
            }
            for j in jobs
        ]
    }
