import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.compliance_sanitizer import compliance_sanitizer

client = TestClient(app)

def test_banned_words_crud_and_preview():
    # 1. 查询违禁词列表
    res = client.get("/api/v1/editor/banned_words")
    assert res.status_code == 200
    data = res.json()
    assert "mappings" in data
    assert data["total"] >= 26
    assert "驾驶证" in data["mappings"]
    assert data["mappings"]["驾驶证"] == "加驶正"

    # 2. 预览测试
    prev_res = client.post(
        "/api/v1/editor/banned_words/preview",
        json={"text": "我们的出证速度是最快的，最低价格"}
    )
    assert prev_res.status_code == 200
    prev_data = prev_res.json()
    assert "蕞快" in prev_data["sanitized_text"]
    assert "蕞低阶格" in prev_data["sanitized_text"]
    assert prev_data["total_matches"] >= 2

    # 3. 添加新的违禁词
    add_res = client.post(
        "/api/v1/editor/banned_words",
        json={"original_word": "科目二包过", "replacement_word": "科目二包合格"}
    )
    assert add_res.status_code == 200
    add_data = add_res.json()
    assert add_data["code"] == 0
    assert add_data["mappings"]["科目二包过"] == "科目二包合格"

    # 验证新词立即参与脱敏
    prev_new = client.post(
        "/api/v1/editor/banned_words/preview",
        json={"text": "咱们驾校科目二包过，无需担心"}
    )
    assert "科目二包合格" in prev_new.json()["sanitized_text"]

    # 4. 删除刚刚添加的违禁词
    del_res = client.delete("/api/v1/editor/banned_words/科目二包过")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["code"] == 0
    assert "科目二包过" not in del_data["mappings"]

    # 5. 恢复默认词库
    reset_res = client.post("/api/v1/editor/banned_words/reset")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["code"] == 0
    assert "驾驶证" in reset_data["mappings"]

def test_batch_cut_endpoints_accept_filter_banned_words(tmp_path):
    from app.native_engine.storage import storage_service
    from app.models.entities import MaterialCategory

    fake_th = tmp_path / "th_batch_banned.mp4"
    fake_th.write_bytes(b"batch_banned_test")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_batch_banned.mp4", fake_th)

    try:
        # 测试 submit 接口接收 filter_banned_words
        res = client.post(
            "/api/v1/batch/submit",
            json={
                "material_ids": [th.id],
                "aspect_ratio": "9:16",
                "filter_banned_words": True
            }
        )
        assert res.status_code == 200
        job_id = res.json()["data"]["job_id"]

        # 查询 batch job 详情
        job_res = client.get(f"/api/v1/batch/jobs/{job_id}")
        assert job_res.status_code == 200
        items = job_res.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["filter_banned_words"] is True
    finally:
        storage_service.delete_material(th.id)


def test_glossary_crud_endpoints():
    # 1. 查询 ASR 纠偏词库
    res = client.get("/api/v1/editor/glossary")
    assert res.status_code == 200
    data = res.json()
    assert "corrections" in data
    assert data["total"] >= 10
    assert "链车" in data["corrections"]
    assert data["corrections"]["链车"] == "练车"

    # 2. 添加或更新纠偏映射
    add_res = client.post(
        "/api/v1/editor/glossary/corrections",
        json={"original_word": "科三路考测试错词", "corrected_word": "科目三路考"}
    )
    assert add_res.status_code == 200
    add_data = add_res.json()
    assert add_data["code"] == 0
    assert add_data["corrections"]["科三路考测试错词"] == "科目三路考"

    # 3. 删除刚刚添加的映射
    del_res = client.delete("/api/v1/editor/glossary/corrections/科三路考测试错词")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["code"] == 0
    assert "科三路考测试错词" not in del_data["corrections"]

    # 4. 恢复默认
    reset_res = client.post("/api/v1/editor/glossary/reset")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["code"] == 0
    assert "链车" in reset_data["corrections"]

