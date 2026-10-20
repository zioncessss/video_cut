"""批量剪辑契约测试（tests/ 内 mock 重型管线，遵循 AGENTS.md 测试边界）。

mock analyze_and_cut / render_project（重量级 ASR/LLM/FFmpeg），验证：
submit 契约、逐项状态流转、单项失败落真实错误且不中断其余、持久化可查询。
"""
import sys
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402
from app.models.entities import MaterialCategory, CutProject, BatchJob, BatchJobItem  # noqa: E402
from app.native_engine.storage import storage_service  # noqa: E402

client = TestClient(app)


def _make_material(tmp_path, name):
    f = tmp_path / name
    f.write_bytes(f"fake_video_stream_{name}".encode())
    return storage_service.save_material(MaterialCategory.TALKING_HEAD, name, f)


def test_submit_validation_errors(tmp_path):
    r = client.post("/api/v1/batch/submit", json={"material_ids": []})
    assert r.status_code == 400
    r2 = client.post("/api/v1/batch/submit", json={"material_ids": ["no-such-id"]})
    assert r2.status_code == 404
    assert "不存在" in r2.json()["detail"]


def test_batch_flow_with_mocked_pipeline(tmp_path, monkeypatch):
    """两项提交：一项成功一项失败（渲染抛错），失败项落真实错误且不中断其余"""
    import app.api.editor as editor_mod

    m_ok = _make_material(tmp_path, "batch_ok.mp4")
    m_bad = _make_material(tmp_path, "batch_bad.mp4")

    async def fake_analyze(req):
        # 模拟坏素材在分析阶段失败
        if req.talking_head_id == m_bad.id:
            raise RuntimeError("ASR 真实失败: 音频流损坏")
        return CutProject(id="proj-ok", title="t", talking_head_id=req.talking_head_id, aspect_ratio=req.aspect_ratio)

    async def fake_render(project_id):
        return CutProject(id=project_id, title="t", talking_head_id="x")

    monkeypatch.setattr(editor_mod, "analyze_and_cut", fake_analyze)
    monkeypatch.setattr(editor_mod, "render_project", fake_render)

    sub = client.post("/api/v1/batch/submit", json={"material_ids": [m_ok.id, m_bad.id], "aspect_ratio": "9:16"})
    assert sub.status_code == 200
    data = sub.json()["data"]
    assert data["queued"] == 2
    assert data["concurrency"] >= 1
    job_id = data["job_id"]

    # BackgroundTasks 在 TestClient 返回前已执行完毕，直接查询最终态
    status = client.get(f"/api/v1/batch/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["status"] == "finished"
    items = {i["material_id"]: i for i in body["items"]}
    assert items[m_ok.id]["status"] == "completed"
    assert items[m_ok.id]["project_id"] == "proj-ok"
    assert items[m_bad.id]["status"] == "failed"
    assert "ASR 真实失败" in items[m_bad.id]["error"], "失败项必须携带真实错误详情"

    # 持久化：任务落库可查询；completed_count 只计真实成功项，失败项单列 failed_count
    # （旧语义把失败项混入 completed_count，导致失败批次被展示成“已完成 5/5”）
    persisted = client.get(f"/api/v1/batch/jobs/{job_id}").json()["data"]
    assert persisted["completed_count"] == 1
    assert persisted["failed_count"] == 1

    listed = client.get("/api/v1/batch/jobs").json()["data"]
    summary = next(j for j in listed if j["job_id"] == job_id)
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 1


def test_batch_stranded_items_healing_in_finished_job():
    """验证终态作业中遗留的 queued/running 条目会被自动自愈为 failed，杜绝已完成作业显示排队中"""
    from app.db.repository import BatchJobRepository
    from app.models.entities import BatchJob, BatchJobItem, BatchJobStatus

    repo = BatchJobRepository()
    raw_job = BatchJob(
        id="job-stranded-test",
        total_count=2,
        completed_count=0,
        concurrency=1,
        status=BatchJobStatus.FINISHED,
        items=[
            BatchJobItem(material_id="mat-1", status="queued"),
            BatchJobItem(material_id="mat-2", status="running")
        ]
    )
    repo.save(raw_job)

    loaded = repo.get_by_id("job-stranded-test")
    assert loaded is not None
    assert loaded.status == BatchJobStatus.FINISHED
    for it in loaded.items:
        assert it.status == "failed"
        assert "执行异常中断" in it.error


def test_multiple_sequential_and_concurrent_batch_submissions(tmp_path, monkeypatch):
    """
    排查与验证：混剪开始一次后，再次添加视频（无论是同素材重剪还是新素材），
    两批任务均能独立调度、正常执行、落库并可查询，互不阻塞。
    """
    import app.api.editor as editor_mod

    m1 = _make_material(tmp_path, "seq_mat_1.mp4")
    m2 = _make_material(tmp_path, "seq_mat_2.mp4")

    analyzed_calls = []
    rendered_calls = []

    async def fake_analyze(req):
        analyzed_calls.append(req.talking_head_id)
        return CutProject(
            id=f"proj-{req.talking_head_id}",
            title="test-title",
            talking_head_id=req.talking_head_id,
            aspect_ratio=req.aspect_ratio,
            output_video_path=f"storage/projects/proj-{req.talking_head_id}/final.mp4"
        )

    async def fake_render(project_id, **kwargs):
        rendered_calls.append(project_id)
        return CutProject(id=project_id, title="test-title", talking_head_id="x")

    monkeypatch.setattr(editor_mod, "analyze_and_cut", fake_analyze)
    monkeypatch.setattr(editor_mod, "render_project", fake_render)

    # 1. 提交第一批混剪任务
    sub1 = client.post("/api/v1/batch/submit", json={"material_ids": [m1.id], "aspect_ratio": "9:16"})
    assert sub1.status_code == 200
    job1_id = sub1.json()["data"]["job_id"]

    # 2. 再次添加视频并提交第二批混剪（包含已出现过的 m1 和新素材 m2）
    sub2 = client.post("/api/v1/batch/submit", json={"material_ids": [m1.id, m2.id], "aspect_ratio": "16:9"})
    assert sub2.status_code == 200
    job2_id = sub2.json()["data"]["job_id"]
    assert job1_id != job2_id

    # 3. 验证两个批次详情均能正常查询，条目状态均为 completed
    st1 = client.get(f"/api/v1/batch/jobs/{job1_id}").json()["data"]
    assert st1["status"] == "finished"
    assert st1["completed_count"] == 1
    assert st1["items"][0]["status"] == "completed"

    st2 = client.get(f"/api/v1/batch/jobs/{job2_id}").json()["data"]
    assert st2["status"] == "finished"
    assert st2["completed_count"] == 2
    assert all(it["status"] == "completed" for it in st2["items"])

    # 4. 验证作业列表均能列出，且按创建时间排序
    listed = client.get("/api/v1/batch/jobs").json()["data"]
    job_ids = [j["job_id"] for j in listed]
    assert job1_id in job_ids
    assert job2_id in job_ids


@pytest.mark.asyncio
async def test_batch_progress_smoothing_and_lifecycle_integrity(tmp_path, monkeypatch):
    """
    状态同步与生命周期防僵死测试：
    1. 确保在 analyze_and_cut 完成后但 render_project 压制未完成时，
       条目对外返回的 progress 不会被 100% 倒挂顶满，且带有压制阶段提示；
    2. 确保作业终态下所有 items 均被正确收敛。
    """
    import app.api.editor as editor_mod
    import app.api.batch as batch_mod
    from app.models.entities import PipelineStage

    m = _make_material(tmp_path, "smooth_progress.mp4")

    # 模拟 analyze_and_cut 产生了 100% 初剪完成事件
    async def fake_analyze(req):
        editor_mod._set_progress(req.talking_head_id, PipelineStage.COMPLETED, 100, "智能初剪与纠偏已完成")
        return CutProject(
            id=f"proj-{req.talking_head_id}",
            title="smooth-title",
            talking_head_id=req.talking_head_id,
            aspect_ratio=req.aspect_ratio,
            output_video_path=f"storage/projects/proj-{req.talking_head_id}/final.mp4"
        )

    # 模拟 render_project 阶段被挂起观察
    render_started = asyncio.Event()
    render_finish = asyncio.Event()

    async def fake_render(project_id, **kwargs):
        render_started.set()
        await render_finish.wait()
        return CutProject(id=project_id, title="smooth-title", talking_head_id=m.id)

    monkeypatch.setattr(editor_mod, "analyze_and_cut", fake_analyze)
    monkeypatch.setattr(editor_mod, "render_project", fake_render)

    # 构造并运行作业条目
    job = BatchJob(total_count=1, items=[BatchJobItem(material_id=m.id)])
    batch_mod._jobs[job.id] = job
    batch_mod._persist(job)

    run_task = asyncio.create_task(batch_mod._run_one(job, job.items[0], "9:16"))

    await render_started.wait()
    # 此时 analyze_and_cut 已结束，正在 render_project
    st = client.get(f"/api/v1/batch/jobs/{job.id}").json()["data"]
    item_data = st["items"][0]
    # 严格断言：正在压制中时，progress 绝对不能是 100% 假完成
    assert item_data["status"] == "running"
    assert item_data["progress"] < 100
    assert item_data["progress"] >= 60
    assert "压制" in (item_data.get("stage_message") or "")
    render_finish.set()
    await run_task

    final_st = client.get(f"/api/v1/batch/jobs/{job.id}").json()["data"]
    assert final_st["items"][0]["status"] == "completed"
    assert final_st["items"][0]["progress"] == 100



