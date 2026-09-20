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
from app.native_engine.project_storage import project_storage_service

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
        json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": True, "enable_scene_decision": False}
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

def test_instruction_apply_endpoint(tmp_path, monkeypatch):
    fake_th_file = tmp_path / "th_inst.mp4"
    fake_th_file.write_bytes(b"stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_inst.mp4", fake_th_file)

    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": True, "enable_scene_decision": False}
    )
    project_id = res.json()["id"]

    # 测试边界（AGENTS.md）：Tier B 指令理解必须 mock，禁止真实 codex/zcode 联网调用
    from app.harness_bridge.base import HarnessInstructionRequest, HarnessPlanResponse

    class FakeTierB:
        async def apply_natural_instruction(self, req: HarnessInstructionRequest):
            return HarnessPlanResponse(
                explanation="已将第1句文案润色为热烈开场（mock）",
                updated_subtitles=None,
                updated_brolls=None,
                harness_engine_used="mock-tier-b",
                latency_ms=1.0
            )

    monkeypatch.setattr("app.api.instruction.get_tier_b_harness", lambda: FakeTierB())

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
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
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
            json={"talking_head_id": th.id, "force_retranscribe": False, "enable_scene_decision": False}
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
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
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

def test_redecide_scenes_dual_layer_api(tmp_path):
    """测试既有工程单独重排分镜接口：双层 60%~70% 编排且保护开场 1.8s"""
    from app.native_engine.project_storage import project_storage_service
    fake_th = tmp_path / "th_redecide.mp4"
    fake_th.write_bytes(b"stream_redecide")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_redecide.mp4", fake_th)

    fake_v = tmp_path / "v_mat.mp4"
    fake_v.write_bytes(b"v_mat")
    mat_v = storage_service.save_material(MaterialCategory.VENUE, "v_mat.mp4", fake_v)

    fake_l = tmp_path / "l_mat.mp4"
    fake_l.write_bytes(b"l_mat")
    mat_l = storage_service.save_material(MaterialCategory.LESSON, "l_mat.mp4", fake_l)

    try:
        cut_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        assert cut_res.status_code == 200
        proj_id = cut_res.json()["id"]

        # 调用 redecide-scenes 接口重排分镜
        res = client.post(
            f"/api/v1/projects/{proj_id}/scene-decision",
            json={"target_coverage": 0.65}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["code"] == 0
        assert "broll_replacements" in data["data"]
        brolls = data["data"]["broll_replacements"]
        assert len(brolls) > 0
        # 验证开场 1.8s 没有被侵犯
        assert not any(b["start_time"] < 1.8 for b in brolls)
    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)
        storage_service.delete_material(mat_v.id)
        storage_service.delete_material(mat_l.id)

def test_cover_upload_and_manifest_generation(tmp_path):
    """测试自定义封面上传与 project_manifest.json 自动维护"""
    from app.native_engine.project_storage import project_storage_service
    from app.core.config import STORAGE_DIR

    fake_th = tmp_path / "th_manifest.mp4"
    fake_th.write_bytes(b"stream_cover_manifest")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_manifest.mp4", fake_th)

    try:
        # 1. 触发初剪
        cut_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        assert cut_res.status_code == 200
        proj = cut_res.json()
        proj_id = proj["id"]
        assert proj["task_dir"] is not None

        task_path = STORAGE_DIR.parent / proj["task_dir"]
        manifest_path = task_path / "project_manifest.json"
        assert manifest_path.exists()
        import json
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data["project_id"] == proj_id

        # 2. 上传自定义封面图片
        fake_img_bytes = b"\xff\xd8\xff\xe0" + b"fake_jpg_binary_stream"
        upload_res = client.post(
            f"/api/v1/projects/{proj_id}/cover/upload",
            files={"file": ("custom_cover.jpg", fake_img_bytes, "image/jpeg")}
        )
        assert upload_res.status_code == 200
        up_data = upload_res.json()
        assert up_data["code"] == 0
        assert up_data["data"]["cover_source"] == "upload"
        assert "cover.jpg" in up_data["data"]["cover_image_path"]

        # 3. 验证 manifest 索引中也同步更新了封面
        manifest_data_v2 = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest_data_v2["cover_source"] == "upload"
        assert manifest_data_v2["cover_image_path"] == up_data["data"]["cover_image_path"]

    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)


def test_render_with_custom_video_speed(tmp_path):
    """验证用户在导出/渲染时自选任意浮点倍速（如 1.12x），系统能够持久化该倍速并完成压制"""
    fake_th_file = tmp_path / "speed_test_th.mp4"
    fake_th_file.write_bytes(b"speed_test_video_stream")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "speed_test_th.mp4", fake_th_file)

    try:
        # 创建工程
        create_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={
                "talking_head_id": th.id,
                "aspect_ratio": "9:16",
                "auto_broll": False,
                "enable_scene_decision": False
            }
        )
        assert create_res.status_code == 200
        proj_id = create_res.json()["id"]

        # 指定自定义导出倍速 1.12x 调用渲染
        render_res = client.post(f"/api/v1/projects/{proj_id}/render?video_speed=1.12")
        assert render_res.status_code == 200
        render_data = render_res.json()
        assert render_data["status"] == "completed"
        assert render_data["strategy"]["video_speed"] == 1.12

        # 权威库回读验证
        get_res = client.get(f"/api/v1/projects/{proj_id}")
        assert get_res.status_code == 200
        assert get_res.json()["strategy"]["video_speed"] == 1.12
    finally:
        project_storage_service.delete_project_by_material(th.id)
        storage_service.delete_material(th.id)


def test_delete_project_endpoint(tmp_path):
    """验证单工程删除接口能够清理 SQLite 数据库记录、内存缓存并清理任务专属目录"""
    from app.core.config import STORAGE_DIR
    fake_th = tmp_path / "delete_test_th.mp4"
    fake_th.write_bytes(b"stream_for_delete_test")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "delete_test_th.mp4", fake_th)

    try:
        # 1. 创建工程
        create_res = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        assert create_res.status_code == 200
        p_data = create_res.json()
        proj_id = p_data["id"]
        task_dir = p_data.get("task_dir")

        # 模拟生成一个任务目录文件
        task_dir_path = None
        if task_dir:
            task_dir_path = (STORAGE_DIR.parent / task_dir).resolve()
            task_dir_path.mkdir(parents=True, exist_ok=True)
            dummy_file = task_dir_path / "dummy_output.mp4"
            dummy_file.write_bytes(b"dummy")

        # 2. 调用 DELETE 接口删除工程
        del_res = client.delete(f"/api/v1/projects/{proj_id}?delete_files=true")
        assert del_res.status_code == 200
        assert del_res.json()["code"] == 0
        assert del_res.json()["project_id"] == proj_id

        # 3. 验证 SQLite 权威库中已被删除
        get_res = client.get(f"/api/v1/projects/{proj_id}")
        assert get_res.status_code == 404

        # 4. 验证任务目录已从磁盘清理
        if task_dir_path:
            assert not task_dir_path.exists()

    finally:
        storage_service.delete_material(th.id)


def test_batch_delete_projects_endpoint(tmp_path):
    """验证批量删除工程接口"""
    th1_file = tmp_path / "batch_del_1.mp4"
    th1_file.write_bytes(b"stream1")
    th1 = storage_service.save_material(MaterialCategory.TALKING_HEAD, "batch_del_1.mp4", th1_file)

    th2_file = tmp_path / "batch_del_2.mp4"
    th2_file.write_bytes(b"stream2")
    th2 = storage_service.save_material(MaterialCategory.TALKING_HEAD, "batch_del_2.mp4", th2_file)

    try:
        res1 = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th1.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        res2 = client.post(
            "/api/v1/projects/analyze-and-cut",
            json={"talking_head_id": th2.id, "aspect_ratio": "9:16", "auto_broll": False, "enable_scene_decision": False}
        )
        p1_id = res1.json()["id"]
        p2_id = res2.json()["id"]

        # 批量删除
        batch_res = client.post(
            "/api/v1/projects/batch-delete",
            json={"project_ids": [p1_id, p2_id], "delete_files": True}
        )
        assert batch_res.status_code == 200
        b_data = batch_res.json()
        assert b_data["code"] == 0
        assert b_data["deleted_count"] == 2
        assert p1_id in b_data["deleted_ids"]
        assert p2_id in b_data["deleted_ids"]

        # 验证读取均返回 404
        assert client.get(f"/api/v1/projects/{p1_id}").status_code == 404
        assert client.get(f"/api/v1/projects/{p2_id}").status_code == 404

    finally:
        storage_service.delete_material(th1.id)
        storage_service.delete_material(th2.id)






