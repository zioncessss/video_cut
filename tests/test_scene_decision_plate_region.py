import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import MaterialCategory, CutProject
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service
from app.native_engine.asr_runner import asr_runner

client = TestClient(app)

def test_scene_decision_zero_cross_region_plate_leakage(tmp_path, monkeypatch):
    """
    验证 0 跨市车牌穿帮安全底线：
    当口播识别出湖州地区时，场地和教学空镜必须严格同城匹配（浙E·湖州），
    绝对严禁切入任何异地车牌素材（如浙A·杭州、浙B·宁波）。
    """
    from app.harness_bridge.embedded import EmbeddedHarnessBridge
    import app.api.editor as editor_module
    monkeypatch.setattr(editor_module, "get_active_harness", lambda: EmbeddedHarnessBridge())

    # 1. 准备测试视频素材
    th_file = tmp_path / "talking_head_huzhou.mp4"
    th_file.write_bytes(b"th_huzhou_video_bytes")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_huzhou.mp4", th_file)

    # 湖州场地与教学（匹配目标城市）
    v_hz_file = tmp_path / "venue_huzhou.mp4"
    v_hz_file.write_bytes(b"venue_hz_bytes")
    v_hz = storage_service.save_material(MaterialCategory.VENUE, "venue_hz.mp4", v_hz_file, plate_region="浙E·湖州")

    l_hz_file = tmp_path / "lesson_huzhou.mp4"
    l_hz_file.write_bytes(b"lesson_hz_bytes")
    l_hz = storage_service.save_material(MaterialCategory.LESSON, "lesson_hz.mp4", l_hz_file, plate_region="浙E·湖州")

    # 异地场地与教学（杭州、宁波车牌，绝不可泄露）
    v_hangzhou_file = tmp_path / "venue_hangzhou.mp4"
    v_hangzhou_file.write_bytes(b"venue_hangzhou_bytes")
    v_hangzhou = storage_service.save_material(MaterialCategory.VENUE, "venue_hangzhou.mp4", v_hangzhou_file, plate_region="浙A·杭州")

    l_ningbo_file = tmp_path / "lesson_ningbo.mp4"
    l_ningbo_file.write_bytes(b"lesson_ningbo_bytes")
    l_ningbo = storage_service.save_material(MaterialCategory.LESSON, "lesson_ningbo.mp4", l_ningbo_file, plate_region="浙B·宁波")

    # 2. Mock ASR 产生湖州学车口播转写文本
    huzhou_subtitles = [
        {
            "start_time": 0.0,
            "end_time": 3.0,
            "raw_text": "今天来到湖州安吉学车训练场",
            "corrected_text": "今天来到湖州安吉学车训练场",
            "words": []
        },
        {
            "start_time": 3.2,
            "end_time": 6.5,
            "raw_text": "带大家看看科目二倒车入库和坡道起步教学",
            "corrected_text": "带大家看看科目二倒车入库和坡道起步教学",
            "words": []
        },
        {
            "start_time": 6.8,
            "end_time": 10.0,
            "raw_text": "在湖州考驾照一定要记牢这些点位",
            "corrected_text": "在湖州考驾照一定要记牢这些点位",
            "words": []
        }
    ]
    monkeypatch.setattr(asr_runner, "transcribe", lambda p: huzhou_subtitles)

    # 3. 运行 analyze-and-cut
    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={
            "talking_head_id": th.id,
            "aspect_ratio": "9:16",
            "auto_broll": True,
            "enable_scene_decision": False,
            "force_retranscribe": True
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    project_id = data["id"]

    # 断言目标城市被正确推导为 "浙E·湖州"
    assert data.get("target_region") == "浙E·湖州"

    # 断言所有已分配的空镜替换中，绝无异地车牌
    brolls = data.get("broll_replacements", [])
    for b in brolls:
        mat_id = b["material_id"]
        assert mat_id != v_hangzhou.id, "违规混入了杭州浙A场地素材！"
        assert mat_id != l_ningbo.id, "违规混入了宁波浙B教学素材！"
        # 若是场地或教学，必须是湖州
        if b["material_category"] == MaterialCategory.VENUE.value:
            assert mat_id == v_hz.id
        elif b["material_category"] == MaterialCategory.LESSON.value:
            assert mat_id == l_hz.id

    # 4. 测试重新分镜 (scene-decision) 同样满足 0 跨市穿帮
    redecide_res = client.post(
        f"/api/v1/projects/{project_id}/scene-decision",
        json={"target_coverage": 0.8}
    )
    assert redecide_res.status_code == 200, redecide_res.text
    redecide_data = redecide_res.json()["data"]
    redecide_brolls = redecide_data.get("broll_replacements", [])
    for b in redecide_brolls:
        mat_id = b["material_id"]
        assert mat_id != v_hangzhou.id, "重新分镜违规混入了杭州浙A场地素材！"
        assert mat_id != l_ningbo.id, "重新分镜违规混入了宁波浙B教学素材！"

    # 清理
    storage_service.delete_material(th.id)
    storage_service.delete_material(v_hz.id)
    storage_service.delete_material(l_hz.id)
    storage_service.delete_material(v_hangzhou.id)
    storage_service.delete_material(l_ningbo.id)

def test_scene_decision_rejects_foreign_when_local_missing(tmp_path, monkeypatch):
    """
    当口播识别出湖州地区，但素材库中没有任何湖州素材、仅有杭州浙A素材时，
    系统宁可保留真人画面或无空镜，绝对不回退到异地车牌素材。
    """
    th_file = tmp_path / "th_huzhou_only_hangzhou_stock.mp4"
    th_file.write_bytes(b"th_huzhou_bytes_stock")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "th_stock.mp4", th_file)

    # 仅录入杭州浙A素材
    v_hz = storage_service.save_material(MaterialCategory.VENUE, "v_hz.mp4", th_file, plate_region="浙A·杭州")
    l_hz = storage_service.save_material(MaterialCategory.LESSON, "l_hz.mp4", th_file, plate_region="浙A·杭州")

    huzhou_subtitles = [
        {"start_time": 0.0, "end_time": 4.0, "raw_text": "这里是浙江湖州德清学车大本营", "corrected_text": "这里是浙江湖州德清学车大本营", "words": []},
        {"start_time": 4.5, "end_time": 9.0, "raw_text": "想在湖州学车的学员注意看动作细节", "corrected_text": "想在湖州学车的学员注意看动作细节", "words": []}
    ]
    monkeypatch.setattr(asr_runner, "transcribe", lambda p: huzhou_subtitles)

    res = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={
            "talking_head_id": th.id,
            "aspect_ratio": "9:16",
            "auto_broll": True,
            "enable_scene_decision": False,
            "force_retranscribe": True
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("target_region") == "浙E·湖州"

    # 杭州素材必须 100% 被过滤掉，broll_replacements 绝不能包含它们
    brolls = data.get("broll_replacements", [])
    for b in brolls:
        assert b["material_id"] != v_hz.id
        assert b["material_id"] != l_hz.id

    storage_service.delete_material(th.id)
    storage_service.delete_material(v_hz.id)
    storage_service.delete_material(l_hz.id)
