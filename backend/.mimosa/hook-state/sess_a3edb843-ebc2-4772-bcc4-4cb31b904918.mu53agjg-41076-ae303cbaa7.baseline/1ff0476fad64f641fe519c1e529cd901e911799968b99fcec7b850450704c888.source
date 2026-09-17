import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List

from app.models.entities import BatchJob
from app.core.batch_queue import batch_manager

router = APIRouter()

class CreateBatchJobRequest(BaseModel):
    total_count: int = 5
    concurrency_limit: int = 0

@router.post("/jobs", response_model=BatchJob)
async def create_batch_job(req: CreateBatchJobRequest, bg_tasks: BackgroundTasks):
    job = batch_manager.create_job(req.total_count, req.concurrency_limit)
    bg_tasks.add_task(batch_manager.run_batch_simulation, job.id)
    return job

@router.get("/jobs", response_model=List[BatchJob])
async def list_batch_jobs():
    return batch_manager.list_jobs()

@router.get("/jobs/{job_id}", response_model=BatchJob)
async def get_batch_job(job_id: str):
    job = batch_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return job
