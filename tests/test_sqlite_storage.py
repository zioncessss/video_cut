import pytest
import sqlite3
import time as _time
from pathlib import Path
from app.db.session import init_db, get_db_connection
from app.db.repository import MaterialRepository, ProjectRepository, SettingsRepository
from app.db.migrator import migrate_legacy_data
from app.models.entities import (
    Material, MaterialCategory, CutProject, CutProjectStatus, SubtitleSegment, EditingStrategy,
    BrollReplacement,
)

@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_videocut.db"
    init_db(db_file)
    return db_file

def test_project_roundtrip_preserves_ai_meta_and_broll_windows(test_db):
    """Stage1 回归：保存→SQLite 重载后，AI 纠偏元数据与编排分镜时间线必须完整还原（不再丢失）"""
    mrepo = MaterialRepository(test_db)
    repo = ProjectRepository(test_db)
    m = Material(category=MaterialCategory.TALKING_HEAD, filename="t.mp4",
                 filepath="storage/materials/talking_head/t.mp4", duration=20.0, created_at=_time.time())
    mrepo.save(m)

    broll = BrollReplacement(start_time=0.5, end_time=4.5, material_id="mat-x",
                             material_category=MaterialCategory.VENUE, playback_mode="loop")
    p = CutProject(
        title="roundtrip", talking_head_id=m.id,
        subtitles=[SubtitleSegment(start_time=0.0, end_time=3.0, raw_text="原始句", corrected_text="修正句")],
        broll_replacements=[broll],
        corrections_summary=[{
            "subtitle_id": "s1", "original_text": "航州", "corrected_text": "湖州",
            "changes": [{"from": "航州", "to": "湖州", "reason": "语义纠错"}],
        }],
        last_engine_used="api",
        correction_latency_ms=123.4,
        status=CutProjectStatus.DRAFT,
    )
    repo.save(p)
    loaded = repo.get_by_id(p.id)
    assert loaded.last_engine_used == "api", "AI 纠偏引擎标注不得在重载后丢失"
    assert loaded.correction_latency_ms == 123.4
    assert loaded.corrections_summary[0]["corrected_text"] == "湖州"
    # 分镜时间线从 brolls_json 完整还原（含 id 与 playback_mode，旧实现会丢失）
    lb = loaded.broll_replacements[0]
    assert lb.id == broll.id
    assert lb.playback_mode == "loop"
    assert abs(lb.end_time - 4.5) < 1e-6
    assert lb.material_category == MaterialCategory.VENUE

def test_sqlite_init_and_wal_mode(test_db):
    with get_db_connection(test_db) as conn:
        cur = conn.execute("PRAGMA journal_mode;")
        row = cur.fetchone()
        assert row[0].lower() == "wal"

        # 验证表已创建
        cur_tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur_tables.fetchall()]
        assert "materials" in tables
        assert "projects" in tables
        assert "subtitles" in tables
        assert "strategies" in tables
        assert "settings" in tables

def test_material_repository_crud(test_db):
    repo = MaterialRepository(test_db)
    mat = Material(
        category=MaterialCategory.TALKING_HEAD,
        filename="test_th.mp4",
        filepath="storage/materials/talking_head/test_th.mp4",
        duration=15.5
    )
    saved = repo.save(mat)
    assert saved.id == mat.id

    fetched = repo.get_by_id(mat.id)
    assert fetched is not None
    assert fetched.filename == "test_th.mp4"
    assert fetched.category == MaterialCategory.TALKING_HEAD

    listed = repo.list_all(category=MaterialCategory.TALKING_HEAD)
    assert any(m.id == mat.id for m in listed)

    deleted = repo.delete(mat.id)
    assert deleted is True
    assert repo.get_by_id(mat.id) is None

def test_project_repository_crud(test_db):
    mat_repo = MaterialRepository(test_db)
    proj_repo = ProjectRepository(test_db)

    # 1. 创建前置素材
    mat = Material(
        category=MaterialCategory.TALKING_HEAD,
        filename="th_for_proj.mp4",
        filepath="storage/materials/talking_head/th_for_proj.mp4",
        duration=30.0
    )
    mat_repo.save(mat)

    # 2. 创建工程
    subs = [
        SubtitleSegment(id="sub-1", start_time=0.0, end_time=2.0, raw_text="欢迎练车", corrected_text="欢迎练车", matched_keywords=["练车"]),
        SubtitleSegment(id="sub-2", start_time=2.0, end_time=5.0, raw_text="科目二考试", corrected_text="科目二考试", matched_keywords=["科目二"])
    ]
    strat = EditingStrategy(banner_main_title="考试必过", font_size="large")
    proj = CutProject(
        title="测试工程",
        talking_head_id=mat.id,
        subtitles=subs,
        strategy=strat
    )

    proj_repo.save(proj)

    # 3. 按 ID 查询
    fetched_by_id = proj_repo.get_by_id(proj.id)
    assert fetched_by_id is not None
    assert fetched_by_id.title == "测试工程"
    assert len(fetched_by_id.subtitles) == 2
    assert fetched_by_id.subtitles[1].corrected_text == "科目二考试"
    assert fetched_by_id.strategy.banner_main_title == "考试必过"

    # 4. 按素材 ID 查询 (1:1 强绑定)
    fetched_by_mat = proj_repo.get_by_material_id(mat.id)
    assert fetched_by_mat is not None
    assert fetched_by_mat.id == proj.id

    # 5. 删除
    assert proj_repo.delete_by_material(mat.id) is True
    assert proj_repo.get_by_id(proj.id) is None

def test_project_repository_single_authority_and_width_fields(test_db):
    mat_repo = MaterialRepository(test_db)
    proj_repo = ProjectRepository(test_db)

    mat = Material(
        category=MaterialCategory.TALKING_HEAD,
        filename="mat_single_auth.mp4",
        filepath="storage/materials/talking_head/mat_single_auth.mp4",
        duration=20.0
    )
    mat_repo.save(mat)

    # 1. 建立旧工程
    old_proj = CutProject(
        id="old-proj-uuid-111",
        title="旧未纠错工程",
        talking_head_id=mat.id,
        subtitles=[SubtitleSegment(id="s1", start_time=0.0, end_time=1.0, raw_text="福州价效", corrected_text="福州价效")],
        strategy=EditingStrategy(banner_main_title="旧标题")
    )
    proj_repo.save(old_proj)

    # 验证旧工程已落库
    assert proj_repo.get_by_material_id(mat.id).id == "old-proj-uuid-111"

    # 2. 建立新纠错工程（带 banner_width_percent 与 subtitle_width_percent）
    new_proj = CutProject(
        id="new-proj-uuid-222",
        title="新纠错工程",
        talking_head_id=mat.id,
        subtitles=[SubtitleSegment(id="s1", start_time=0.0, end_time=1.0, raw_text="福州价效", corrected_text="湖州驾校")],
        strategy=EditingStrategy(
            banner_main_title="新标题",
            banner_width_percent=85,
            subtitle_width_percent=78
        )
    )
    proj_repo.save(new_proj)

    # 验证唯一权威性：旧工程必须已被自动删除，查出来的必定是新工程
    current = proj_repo.get_by_material_id(mat.id)
    assert current.id == "new-proj-uuid-222"
    assert current.subtitles[0].corrected_text == "湖州驾校"
    assert current.strategy.banner_width_percent == 85
    assert current.strategy.subtitle_width_percent == 78
    assert proj_repo.get_by_id("old-proj-uuid-111") is None

