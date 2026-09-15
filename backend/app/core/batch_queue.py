import asyncio
from typing import Dict, List, Any
from app.models.entities import BatchJob, BatchJobStatus
from app.core.resource import get_hardware_metrics

class BatchQueueManager:
    def __init__(self):
        self._jobs: Dict[str, BatchJob] = {}

    def create_job(self, total_count: int, user_concurrency: int = 0) -> BatchJob:
        metrics = get_hardware_metrics()
        # 若未指定并发，自动采用系统推荐安全并发槽位
        concurrency = user_concurrency if user_concurrency > 0 else metrics.recommended_concurrency
        job = BatchJob(
            total_count=total_count,
            completed_count=0,
            concurrency=concurrency,
            status=BatchJobStatus.QUEUED
        )
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> BatchJob:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[BatchJob]:
        return list(self._jobs.values())

    async def run_batch_simulation(self, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.status = BatchJobStatus.RUNNING
        sem = asyncio.Semaphore(job.concurrency)

        async def worker():
            async with sem:
                await asyncio.sleep(0.1)  # 模拟单条视频合成
                job.completed_count += 1

        tasks = [worker() for _ in range(job.total_count)]
        await asyncio.gather(*tasks)
        job.status = BatchJobStatus.FINISHED

batch_manager = BatchQueueManager()
