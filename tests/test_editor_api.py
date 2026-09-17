import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory
from app.native_engine.storage import storage_service

client = TestClient(app)

def test_editor_analyze_and_render_flow(tmp_path):
    # 1. 创建并保存一个口播视频素材和一个场地视频素材
    fake_th_file = tmp_path / "talking_head.mp4"
    fake_th_file.write_bytes(b"fake_talking_head_video_stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "talking_head.mp4", fake_th_file)

    fake_venue_file = tmp_path / "venue.mp4"
    fake_venue_file.write_bytes(b"fake_venue_video_stream")
    venue = storage_service.save_material(MaterialCategory.VENUE, "venue.mp4", fake_venue_file)

    # 2. 调用 /analyze-and-cut
    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": True}
    )
    assert res.status_code == 200
    proj_data = res.json()
    project_id = proj_data["id"]
    assert len(proj_data["subtitles"]) > 0
    assert proj_data["status"] == "draft"

    # 3. 验证字幕修改
    subtitles = proj_data["subtitles"]
    subtitles[0]["corrected_text"] = "修改后的第一句字幕"
    put_res = client.put(
        f"/api/v1/projects/{project_id}/subtitles",
        json={"subtitles": subtitles}
    )
    assert put_res.status_code == 200
    assert put_res.json()["subtitles"][0]["corrected_text"] == "修改后的第一句字幕"

    # 4. 调用渲染
    render_res = client.post(f"/api/v1/projects/{project_id}/render")
    assert render_res.status_code == 200
    render_data = render_res.json()
    assert render_data["status"] == "completed"
    assert render_data["output_video_path"] is not None

    # 清理
    storage_service.delete_material(th.id)
    storage_service.delete_material(venue.id)

def test_editor_correct_endpoint(monkeypatch):
    # 端点测试固定走 embedded 词库引擎：确定性断言，不依赖真实 codex CLI 的 LLM 输出波动
    from app.harness_bridge.embedded import EmbeddedHarnessBridge
    import app.api.editor as editor_module
    monkeypatch.setattr(editor_module, "get_active_harness", lambda: EmbeddedHarnessBridge())

    subs = [
        {"id": "sub-1", "start_time": 0.0, "end_time": 2.5, "raw_text": "练科尔到库技巧", "corrected_text": "练科尔到库技巧"}
    ]
    res = client.post(
        "/api/v1/editor/correct",
        json={"subtitles": subs, "domain": "driving_school"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["code"] == 0
    assert len(data["data"]["subtitles"]) == 1
    assert "科目二" in data["data"]["subtitles"][0]["corrected_text"]

def test_instruction_apply_endpoint(tmp_path):
    fake_th_file = tmp_path / "th_inst.mp4"
    fake_th_file.write_bytes(b"stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_inst.mp4", fake_th_file)

    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": True}
    )
    project_id = res.json()["id"]

    inst_res = client.post(
        "/api/v1/instruction/apply",
        json={"project_id": project_id, "instruction": "把第1句文案润色为热烈开场"}
    )
    assert inst_res.status_code == 200
    inst_data = inst_res.json()
    assert inst_data["explanation"] != ""
    assert "harness_engine_used" in inst_data

    storage_service.delete_material(th.id)

def test_project_storage_and_material_binding(tmp_path):
    from app.native_engine.project_storage import project_storage_service
    fake_th = tmp_path / "talking_binding.mp4"
    fake_th.write_bytes(b"short_fake_stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "talking_binding.mp4", fake_th)

    try:
        # 1. 未分析前查询工程，应返回 404
        get_res1 = client.get(f"/api/v1/projects/by-material/{th.id}")
        assert get_res1.status_code == 404

        # 2. 执行初剪与 ASR 生成工程
        cut_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False}
        )
        assert cut_res.status_code == 200
        proj_data = cut_res.json()
        assert proj_data["talking_head_id"] == th.id
        assert len(proj_data["subtitles"]) > 0

        # 3. 再次查询，应命中磁盘缓存秒级返回 200
        get_res2 = client.get(f"/api/v1/projects/by-material/{th.id}")
        assert get_res2.status_code == 200
        cached_proj = get_res2.json()
        assert cached_proj["id"] == proj_data["id"]
        assert len(cached_proj["subtitles"]) == len(proj_data["subtitles"])

        # 4. 非强制重算时，直接返回已有工程
        cut_res_cached = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "force_retranscribe": False}
        )
        assert cut_res_cached.status_code == 200
        assert cut_res_cached.json()["id"] == proj_data["id"]

    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)

def test_versioned_render_replacement_and_progress(tmp_path):
    from app.native_engine.project_storage import project_storage_service
    fake_th = tmp_path / "th_versioned.mp4"
    fake_th.write_bytes(b"stream_versioned")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_versioned.mp4", fake_th)

    try:
        # 1. 触发初剪并验证进度接口
        cut_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False}
        )
        assert cut_res.status_code == 200
        proj = cut_res.json()
        project_id = proj["id"]

        # 2. 查询进度
        prog_res = client.get(f"/api/v1/projects/{project_id}/progress")
        assert prog_res.status_code == 200
        prog = prog_res.json()
        assert prog["percent"] == 100
        assert prog["stage"] == "completed"

        # 3. 第一次渲染
        render1 = client.post(f"/api/v1/projects/{project_id}/render")
        assert render1.status_code == 200
        r1_data = render1.json()
        file1 = r1_data["output_filename"]
        assert file1.startswith(f"output_{project_id}")
        assert r1_data["output_file_size_mb"] >= 0

        # 4. 第二次修改字幕并重新渲染，验证新生成产物替代前序版本
        subtitles = r1_data["subtitles"]
        subtitles[0]["corrected_text"] = "第二次编辑字幕"
        client.put(f"/api/v1/projects/{project_id}/subtitles", json={"subtitles": subtitles})

        import time
        time.sleep(1.05) # 确保时间戳发生单调递增跳变

        render2 = client.post(f"/api/v1/projects/{project_id}/render")
        assert render2.status_code == 200
        r2_data = render2.json()
        file2 = r2_data["output_filename"]
        assert file2 != file1
        assert file2.startswith(f"output_{project_id}")

        # 5. 测试 open-folder 接口
        folder_res = client.post(
            "/api/v1/projects/open-folder",
            json={"path": r2_data["output_video_path"]}
        )
        assert folder_res.status_code == 200
        assert folder_res.json()["code"] == 0

    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)


