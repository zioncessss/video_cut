"""字幕主键冲突回归测试（012 分支批量混剪 4/5 失败的根因）。

真实链路中 ASR/纠偏引擎产出确定性字幕编号（s_1..s_N），而 subtitles.id 是
SQLite 全局主键：同批多个素材各自建工程时，第二个工程保存必然撞主键
（UNIQUE constraint failed: subtitles.id），整条批量流水线随之失败且无成片。

本测试固定两条防线（对应 AGENTS.md 测试隔离准则，mock 仅存在于 tests/）：
1. analyze_and_cut 对本次转写字幕一律重生成 uuid4（粗剪/分镜/高光在重生成之后
   按新 ID 关联，链路内自洽）；
2. ProjectRepository.save 保存前防御性重映射冲突 ID（同项目重复 + 跨工程存量
   冲突），原文/高亮词全量保留，绝不静默丢行。
"""
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.main import app  # noqa: E402
from app.models.entities import (  # noqa: E402
    CutProject,
    CutProjectStatus,
    EditingStrategy,
    HighlightWord,
    MaterialCategory,
    SubtitleSegment,
)
from app.db.repository import ProjectRepository  # noqa: E402
from app.native_engine.storage import storage_service  # noqa: E402

client = TestClient(app)


def _make_material(tmp_path, name):
    f = tmp_path / name
    f.write_bytes(f"fake_video_stream_{name}".encode())
    return storage_service.save_material(MaterialCategory.TALKING_HEAD, name, f)


def _deterministic_subs():
    """模拟真实 ASR/纠偏引擎输出：跨工程重复出现的确定性编号 s_1..s_N"""
    return [
        SubtitleSegment(
            id="s_1", start_time=0.0, end_time=2.0,
            raw_text="湖州学车一口价全包", corrected_text="湖州学车一口价全包",
            highlight_words=[HighlightWord(word="湖州", source="glossary", category="location")],
            matched_keywords=["湖州"],
        ),
        SubtitleSegment(
            id="s_2", start_time=2.0, end_time=4.0,
            raw_text="无隐形费用", corrected_text="无隐形费用",
        ),
    ]


def _make_project(material_id: str, title: str) -> CutProject:
    return CutProject(
        title=title,
        talking_head_id=material_id,
        aspect_ratio="9:16",
        subtitles=_deterministic_subs(),
        strategy=EditingStrategy(),
        status=CutProjectStatus.DRAFT,
    )


def test_cross_project_same_deterministic_ids_both_save(tmp_path):
    """两个工程携带完全相同的确定性字幕 ID 依次保存：都必须成功，互不侵占"""
    repo = ProjectRepository()
    m1 = _make_material(tmp_path, "th_a.mp4")
    m2 = _make_material(tmp_path, "th_b.mp4")

    pa = _make_project(m1.id, "工程A")
    pb = _make_project(m2.id, "工程B")
    repo.save(pa)
    # 修复前此处抛 RuntimeError("保存剪辑工程到 SQLite 失败: UNIQUE constraint failed: subtitles.id")
    repo.save(pb)

    row_a = repo.get_by_id(pa.id)
    row_b = repo.get_by_id(pb.id)
    assert row_a is not None and row_b is not None
    assert [s.id for s in row_a.subtitles] == ["s_1", "s_2"]
    assert row_a.subtitles[0].raw_text == "湖州学车一口价全包"

    # 工程B 冲突 ID 被重映射为 uuid，行数与内容全量保留
    assert len(row_b.subtitles) == 2
    assert all(s.id != "s_1" and s.id != "s_2" for s in row_b.subtitles)
    assert row_b.subtitles[0].raw_text == "湖州学车一口价全包"
    # 高亮词零丢失（AGENTS.md 高亮词全生命周期无损准则）
    hw = row_b.subtitles[0].highlight_words
    assert len(hw) == 1 and hw[0].word == "湖州" and hw[0].category == "location"
    # 内存对象与落库行保持一致（客户端后续编辑引用同一 ID）
    assert pb.subtitles[0].id == row_b.subtitles[0].id


def test_within_project_duplicate_ids_all_rows_saved(tmp_path):
    """同项目内出现重复字幕 ID：保存不炸，行数不丢且全部唯一"""
    repo = ProjectRepository()
    m = _make_material(tmp_path, "th_dup.mp4")
    project = _make_project(m.id, "重复ID工程")
    project.subtitles[1].id = "s_1"  # 人为与第一句重复
    repo.save(project)

    loaded = repo.get_by_id(project.id)
    ids = [s.id for s in loaded.subtitles]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert loaded.subtitles[0].raw_text == "湖州学车一口价全包"
    assert loaded.subtitles[1].raw_text == "无隐形费用"


def test_analyze_two_materials_no_pk_collision(tmp_path, monkeypatch):
    """API 级回归：两个素材先后走真实 analyze 链路，确定性 ASR 编号不得撞库"""
    from app.native_engine.asr_runner import asr_runner

    def fake_transcribe(video_path):
        return [
            {
                "id": "s_1", "start_time": 0.0, "end_time": 2.0,
                "raw_text": "测试第一句学车", "corrected_text": "测试第一句学车",
                "words": [{"word": "测试", "start": 0.0, "end": 1.0},
                          {"word": "第一句学车", "start": 1.0, "end": 2.0}],
            },
            {
                "id": "s_2", "start_time": 2.2, "end_time": 5.0,
                "raw_text": "测试第二句费用全透明", "corrected_text": "测试第二句费用全透明",
                "words": [{"word": "测试第二句", "start": 2.2, "end": 3.2},
                          {"word": "费用全透明", "start": 3.2, "end": 5.0}],
            },
        ]

    monkeypatch.setattr(asr_runner, "transcribe", fake_transcribe)

    m1 = _make_material(tmp_path, "pipe_a.mp4")
    m2 = _make_material(tmp_path, "pipe_b.mp4")

    r1 = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": m1.id, "enable_scene_decision": False},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/v1/projects/analyze-and-cut",
        json={"talking_head_id": m2.id, "enable_scene_decision": False},
    )
    # 修复前 r2 返回 500，detail 含 "UNIQUE constraint failed: subtitles.id"
    assert r2.status_code == 200, r2.text

    for resp in (r1, r2):
        ids = [s["id"] for s in resp.json()["subtitles"]]
        assert len(ids) >= 2
        assert all(not str(i).startswith("s_") for i in ids)
        for i in ids:
            uuid.UUID(str(i))  # 必须全部是合法 uuid

    # 两个工程字幕均完整入库
    id1 = {s["id"] for s in r1.json()["subtitles"]}
    id2 = {s["id"] for s in r2.json()["subtitles"]}
    assert id1.isdisjoint(id2)


def test_concurrent_multi_project_save_pk_self_healing(tmp_path):
    """5 个工程完全并发同时调用 save：验证并发微秒级冲突自愈，全量成功保存零丢失"""
    import concurrent.futures

    repo = ProjectRepository()
    projects = []
    for i in range(5):
        m = _make_material(tmp_path, f"concurrent_{i}.mp4")
        p = _make_project(m.id, f"并发工程_{i}")
        # 人为强行将所有工程的字幕 ID 设为完全一致的确定性 short id
        p.subtitles = _deterministic_subs()
        projects.append(p)

    errors = []
    saved_projects = []

    def save_worker(proj):
        try:
            repo.save(proj)
            return proj
        except Exception as e:
            errors.append(str(e))
            raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(save_worker, p) for p in projects]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            saved_projects.append(res)

    assert len(errors) == 0
    assert len(saved_projects) == 5

    # 验证 5 个工程在 SQLite 中全量保存成功，字幕总行数 = 5 * 2 = 10
    total_saved_subs = 0
    all_saved_sub_ids = []
    for p in projects:
        db_p = repo.get_by_id(p.id)
        assert db_p is not None
        assert len(db_p.subtitles) == 2
        total_saved_subs += len(db_p.subtitles)
        all_saved_sub_ids.extend([s.id for s in db_p.subtitles])
        # 验证高亮词无损
        assert db_p.subtitles[0].raw_text == "湖州学车一口价全包"
        assert len(db_p.subtitles[0].highlight_words) == 1
        assert db_p.subtitles[0].highlight_words[0].word == "湖州"

    # 全局主键互不重复
    assert len(all_saved_sub_ids) == 10
    assert len(set(all_saved_sub_ids)) == 10

