import pytest
import sys
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app
from app.models.entities import CutProject, SubtitleSegment, HighlightWord, MaterialCategory, EditingStrategy, PruneSpan
from app.native_engine.storage import storage_service
from app.native_engine.project_storage import project_storage_service

client = TestClient(app)

def test_split_subtitle_by_punctuation(tmp_path):
    """验证按自然标点符号将一段字幕精准拆分为两段，时间戳严格连续衔接"""
    fake_th_file = tmp_path / "split_th.mp4"
    fake_th_file.write_bytes(b"fake_video_stream_for_split")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "split_th.mp4", fake_th_file)

    proj_id = f"proj_split_{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    initial_sub = SubtitleSegment(
        id=sub_id,
        start_time=1.0,
        end_time=5.0,
        raw_text="欢迎来到顺达驾校，今天我们来练习倒车入库",
        corrected_text="欢迎来到顺达驾校，今天我们来练习倒车入库",
        highlight_words=[
            HighlightWord(word="顺达驾校", source="glossary", color="#FACC15"),
            HighlightWord(word="倒车入库", source="glossary", color="#FACC15")
        ],
        matched_keywords=["顺达驾校", "倒车入库"]
    )
    p = CutProject(
        id=proj_id,
        title="字幕拆分测试工程",
        talking_head_id=th.id,
        aspect_ratio="9:16",
        subtitles=[initial_sub],
        strategy=EditingStrategy(enable_highlight=True)
    )
    project_storage_service.save_project(p)

    # 发起拆分请求（缺省参数，自动按逗号智能拆分）
    res = client.post(f"/api/v1/projects/{proj_id}/subtitles/{sub_id}/split")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["split_subtitles"]) == 2

    s1, s2 = data["split_subtitles"]
    # 验证文本拆分
    assert s1["corrected_text"] == "欢迎来到顺达驾校"
    assert s2["corrected_text"] == "今天我们来练习倒车入库"

    # 验证时间戳连续性与无缝承接 (S1.end == S2.start)
    assert s1["start_time"] == 1.0
    assert s1["end_time"] == s2["start_time"]
    assert s2["end_time"] == 5.0
    assert round(s1["end_time"] - s1["start_time"] + s2["end_time"] - s2["start_time"], 2) == 4.0

    # 验证高亮词无损继承
    s1_words = [w["word"] for w in s1.get("highlight_words", [])]
    s2_words = [w["word"] for w in s2.get("highlight_words", [])]
    assert "顺达驾校" in s1_words
    assert "倒车入库" in s2_words

    # 验证 SQLite 权威库同步持久化
    saved = project_storage_service.get_by_project_id(proj_id)
    assert len(saved.subtitles) == 2
    assert saved.subtitles[0].id == sub_id
    assert saved.subtitles[0].corrected_text == "欢迎来到顺达驾校"
    assert saved.subtitles[1].corrected_text == "今天我们来练习倒车入库"

    storage_service.delete_material(th.id)

def test_split_subtitle_custom_text_and_time(tmp_path):
    """验证用户手动指定前后两段文本与精确切分秒数进行拆分"""
    fake_th_file = tmp_path / "split_th2.mp4"
    fake_th_file.write_bytes(b"fake_video_stream_for_split_2")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "split_th2.mp4", fake_th_file)

    proj_id = f"proj_split2_{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    initial_sub = SubtitleSegment(
        id=sub_id,
        start_time=2.0,
        end_time=6.0,
        raw_text="第一段长句子第二段长句子",
        corrected_text="第一段长句子第二段长句子",
        highlight_words=[]
    )
    p = CutProject(
        id=proj_id,
        title="精确指定拆分测试",
        talking_head_id=th.id,
        aspect_ratio="9:16",
        subtitles=[initial_sub],
        strategy=EditingStrategy(enable_highlight=True)
    )
    project_storage_service.save_project(p)

    payload = {
        "part1_text": "第一段自定义文本",
        "part2_text": "第二段自定义文本",
        "split_time": 3.80,
        "is_compact_time": False
    }
    res = client.post(f"/api/v1/projects/{proj_id}/subtitles/{sub_id}/split", json=payload)
    assert res.status_code == 200
    data = res.json()
    s1, s2 = data["split_subtitles"]

    assert s1["corrected_text"] == "第一段自定义文本"
    assert s2["corrected_text"] == "第二段自定义文本"
    assert s1["start_time"] == 2.0
    assert s1["end_time"] == 3.80
    assert s2["start_time"] == 3.80
    assert s2["end_time"] == 6.0

    storage_service.delete_material(th.id)

def test_split_subtitle_with_compact_reprojection(tmp_path):
    """验证在存在粗剪剔除区间 (PruneSpans) 的工程中拆分字幕，双轴正确重投影"""
    fake_th_file = tmp_path / "split_th3.mp4"
    fake_th_file.write_bytes(b"fake_video_stream_for_split_3")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "split_th3.mp4", fake_th_file)

    proj_id = f"proj_split3_{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    initial_sub = SubtitleSegment(
        id=sub_id,
        start_time=2.0,
        end_time=6.0,
        raw_text="开头前置口误已被剪掉，这里是成片正常讲解",
        corrected_text="开头前置口误已被剪掉，这里是成片正常讲解"
    )
    # 模拟开头 0.0~2.0 被剔除
    prune_span = PruneSpan(
        id="prune_head",
        start_time=0.0,
        end_time=2.0,
        duration=2.0,
        reason="head_silence",
        is_active=True
    )
    p = CutProject(
        id=proj_id,
        title="带剔除区间的拆分测试",
        talking_head_id=th.id,
        aspect_ratio="9:16",
        subtitles=[initial_sub],
        prune_spans=[prune_span],
        strategy=EditingStrategy(enable_auto_prune=True)
    )
    project_storage_service.save_project(p)

    # 在成片时间轴 (compact) 上进行拆分，例如在成片 2.0s 处拆分 (成片区间 0.0~4.0s，对应物理 2.0~6.0s)
    res = client.post(
        f"/api/v1/projects/{proj_id}/subtitles/{sub_id}/split",
        json={"split_time": 2.0, "is_compact_time": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["split_subtitles"]) == 2
    assert len(data["compact_subtitles"]) == 2

    c1, c2 = data["compact_subtitles"]
    # 紧凑轴起点应从 0.0 开始
    assert c1["start_time"] == 0.0
    assert c1["end_time"] == c2["start_time"]
    assert c2["end_time"] == 4.0

    storage_service.delete_material(th.id)

def test_split_subtitle_acoustic_word_alignment(tmp_path):
    """验证包含 ASR 字级声学时间戳 (words) 的字幕自动依据文字断句点实现声学毫秒对齐"""
    fake_th_file = tmp_path / "split_th_words.mp4"
    fake_th_file.write_bytes(b"fake_video_stream_words")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "split_th_words.mp4", fake_th_file)

    proj_id = f"proj_words_{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    
    # 模拟真实 ASR 产生的字级时间戳：
    # "同城学车" (1.00s ~ 2.20s), "包教包会" (2.35s ~ 3.50s)
    words = [
        {"word": "同", "start": 1.00, "end": 1.30},
        {"word": "城", "start": 1.30, "end": 1.60},
        {"word": "学", "start": 1.60, "end": 1.90},
        {"word": "车", "start": 1.90, "end": 2.20},
        {"word": "包", "start": 2.35, "end": 2.60},
        {"word": "教", "start": 2.60, "end": 2.90},
        {"word": "包", "start": 2.90, "end": 3.20},
        {"word": "会", "start": 3.20, "end": 3.50},
    ]
    initial_sub = SubtitleSegment(
        id=sub_id,
        start_time=1.00,
        end_time=3.50,
        raw_text="同城学车包教包会",
        corrected_text="同城学车包教包会",
        words=words
    )
    p = CutProject(
        id=proj_id,
        title="声学字级对齐测试",
        talking_head_id=th.id,
        aspect_ratio="9:16",
        subtitles=[initial_sub]
    )
    project_storage_service.save_project(p)

    # 用户仅指定文本拆分点："同城学车" 与 "包教包会"，不指定 split_time
    payload = {
        "part1_text": "同城学车",
        "part2_text": "包教包会"
    }
    res = client.post(f"/api/v1/projects/{proj_id}/subtitles/{sub_id}/split", json=payload)
    assert res.status_code == 200
    data = res.json()
    s1, s2 = data["split_subtitles"]

    # 声学切分点应位于 "车"(end=2.20) 与 "包"(start=2.35) 之间，即 round((2.20+2.35)/2, 2) = 2.28s
    assert s1["end_time"] == s2["start_time"]
    assert abs(s1["end_time"] - 2.28) <= 0.05
    assert len(s1.get("words", [])) == 4
    assert len(s2.get("words", [])) == 4

    storage_service.delete_material(th.id)

def test_merge_next_subtitle(tmp_path):
    """验证当前句与下一句无缝合并，跨度延伸、文本合并与高亮词去重"""
    fake_th_file = tmp_path / "merge_th.mp4"
    fake_th_file.write_bytes(b"fake_video_stream_merge")
    th = storage_service.save_material(MaterialCategory.TALKING_HEAD, "merge_th.mp4", fake_th_file)

    proj_id = f"proj_merge_{uuid.uuid4().hex[:8]}"
    sub1_id = f"sub1_{uuid.uuid4().hex[:8]}"
    sub2_id = f"sub2_{uuid.uuid4().hex[:8]}"

    sub1 = SubtitleSegment(
        id=sub1_id,
        start_time=1.00,
        end_time=2.50,
        raw_text="自建万平训练场",
        corrected_text="自建万平训练场",
        highlight_words=[HighlightWord(word="训练场", source="glossary", color="#FACC15")]
    )
    sub2 = SubtitleSegment(
        id=sub2_id,
        start_time=2.50,
        end_time=4.20,
        raw_text="教练一对一指导",
        corrected_text="教练一对一指导",
        highlight_words=[HighlightWord(word="一对一", source="glossary", color="#FACC15")]
    )
    p = CutProject(
        id=proj_id,
        title="合并下一句测试",
        talking_head_id=th.id,
        aspect_ratio="9:16",
        subtitles=[sub1, sub2]
    )
    project_storage_service.save_project(p)

    res = client.post(f"/api/v1/projects/{proj_id}/subtitles/{sub1_id}/merge-next")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["subtitles"]) == 1

    merged = data["subtitles"][0]
    assert merged["id"] == sub1_id
    assert merged["start_time"] == 1.00
    assert merged["end_time"] == 4.20
    assert "自建万平训练场" in merged["corrected_text"]
    assert "教练一对一指导" in merged["corrected_text"]
    merged_words = [w["word"] for w in merged.get("highlight_words", [])]
    assert "训练场" in merged_words
    assert "一对一" in merged_words

    storage_service.delete_material(th.id)
