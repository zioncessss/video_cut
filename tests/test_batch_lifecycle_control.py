"""
批量混剪生命周期控制与容错测试 (013-system-resilience-ux: US2, FR-202, FR-203)
测试目标：
1. 取消批次：支持取消运行中或排队中的任务，未完成 items 标记为 canceled，符合 contracts/batch-control-api.json。
2. 重试失败项：仅将 status == 'failed' 的条目重新置为 queued，已完成项保持 completed 绝不重复执行。
3. 异常边界：无失败项时重试返回 400 提示。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.entities import BatchJob, BatchJobItem, BatchJobStatus
from app.db.repository import BatchJobRepository
from app.api.batch import _jobs, _running_tasks


@pytest.fixture
def client():
    return TestClient(app)


def test_cancel_batch_job_endpoint(client):
    repo = BatchJobRepository()
    
    # 构造含 3 个排队条目的作业
    items = [
        BatchJobItem(material_id="mat-cancel-1", status="queued"),
        BatchJobItem(material_id="mat-cancel-2", status="queued"),
        BatchJobItem(material_id="mat-cancel-3", status="queued"),
    ]
    job = BatchJob(
        id="job-test-cancel-01",
        total_count=3,
        completed_count=0,
        concurrency=2,
        status=BatchJobStatus.QUEUED,
        items=items
    )
    repo.save(job)
    _jobs[job.id] = job

    # 调用取消接口
    res = client.post(f"/api/v1/batch/jobs/{job.id}/cancel")
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == 0
    assert data["job_id"] == job.id
    assert data["status"] == "canceled"
    assert data["canceled_items_count"] == 3

    # 验证落库持久化状态
    saved_job = repo.get_by_id(job.id)
    assert saved_job is not None
    assert saved_job.status == BatchJobStatus.CANCELED
    for it in saved_job.items:
        assert it.status == "canceled"
        assert "取消" in (it.error or "")


def test_retry_failed_batch_job_endpoint(client):
    repo = BatchJobRepository()
    
    # 构造含 1 个已完成、2 个失败条目的批次
    items = [
        BatchJobItem(material_id="mat-done-1", status="completed", progress=100),
        BatchJobItem(material_id="mat-fail-2", status="failed", error="ASR timeout", progress=40),
        BatchJobItem(material_id="mat-fail-3", status="failed", error="Network error", progress=5),
    ]
    job = BatchJob(
        id="job-test-retry-01",
        total_count=3,
        completed_count=1,
        concurrency=2,
        status=BatchJobStatus.FINISHED,
        items=items
    )
    repo.save(job)
    _jobs[job.id] = job

    from unittest.mock import patch

    with patch("app.api.batch._execute_job") as mock_exec:
        # 调用重试失败项接口
        res = client.post(f"/api/v1/batch/jobs/{job.id}/retry-failed")
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 0
        assert data["job_id"] == job.id
        assert data["retrying_count"] == 2

        # 验证失败项被重置为 queued，已完成项保持 completed
        saved_job = repo.get_by_id(job.id)
        assert saved_job is not None
        assert saved_job.status == BatchJobStatus.QUEUED
        assert saved_job.items[0].status == "completed"
        assert saved_job.items[1].status == "queued"
        assert saved_job.items[1].error is None
        assert saved_job.items[1].progress == 0
        assert saved_job.items[2].status == "queued"
        assert saved_job.items[2].error is None

        mock_exec.assert_called_once_with(job.id, "9:16", 1.0, retry_failed_only=True)


def test_retry_failed_when_no_failed_items_returns_400(client):
    repo = BatchJobRepository()
    
    items = [
        BatchJobItem(material_id="mat-done-1", status="completed", progress=100),
        BatchJobItem(material_id="mat-done-2", status="completed", progress=100),
    ]
    job = BatchJob(
        id="job-test-no-fail",
        total_count=2,
        completed_count=2,
        concurrency=2,
        status=BatchJobStatus.FINISHED,
        items=items
    )
    repo.save(job)
    _jobs[job.id] = job

    res = client.post(f"/api/v1/batch/jobs/{job.id}/retry-failed")
    assert res.status_code == 400
    assert "没有失败条目" in res.json().get("detail", "")


def test_retry_failed_preserves_original_aspect_ratio_and_speed(client):
    """验证重试失败项时自动从已有工程探测并继承原始 16:9 画幅与 1.2x 倍速设置，不被重置"""
    repo = BatchJobRepository()
    from app.native_engine.project_storage import project_storage_service
    from app.models.entities import CutProject, CutProjectStatus, EditingStrategy

    # 创建一个具有 16:9 画幅与 1.2x 速度的已建工程
    proj = CutProject(
        id="proj-custom-ratio-01",
        title="横屏倍速测试工程",
        talking_head_id="mat-th-custom",
        aspect_ratio="16:9",
        strategy=EditingStrategy(video_speed=1.2),
        status=CutProjectStatus.COMPLETED
    )
    project_storage_service.save_project(proj)

    items = [
        BatchJobItem(material_id="mat-th-custom", project_id=proj.id, status="completed", progress=100),
        BatchJobItem(material_id="mat-th-fail", status="failed", error="Transcribe error", progress=30),
    ]
    job = BatchJob(
        id="job-test-custom-retry",
        total_count=2,
        completed_count=1,
        concurrency=2,
        status=BatchJobStatus.FINISHED,
        items=items
    )
    repo.save(job)
    _jobs[job.id] = job

    from unittest.mock import patch
    with patch("app.api.batch._execute_job") as mock_exec:
        res = client.post(f"/api/v1/batch/jobs/{job.id}/retry-failed")
        assert res.status_code == 200
        mock_exec.assert_called_once_with(job.id, "16:9", 1.2, retry_failed_only=True)


def test_retry_queued_items_in_finished_batch(client):
    """验证当批次标记为 finished 但其内部条目仍处于 queued 状态时，也能正确识别并重新执行"""
    repo = BatchJobRepository()

    items = [
        BatchJobItem(material_id="mat-1", status="completed", progress=100),
        BatchJobItem(material_id="mat-2", status="queued", progress=0),
        BatchJobItem(material_id="mat-3", status="queued", progress=0),
    ]
    job = BatchJob(
        id="job-test-stuck-queued",
        total_count=3,
        completed_count=1,
        concurrency=2,
        status=BatchJobStatus.FINISHED,
        items=items
    )
    repo.save(job)
    _jobs[job.id] = job

    from unittest.mock import patch
    with patch("app.api.batch._execute_job") as mock_exec:
        res = client.post(f"/api/v1/batch/jobs/{job.id}/retry-failed")
        assert res.status_code == 200
        data = res.json()
        assert data.get("retrying_count") == 2
        mock_exec.assert_called_once_with(job.id, "9:16", 1.0, retry_failed_only=True)

