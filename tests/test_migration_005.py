"""005 迁移脚本（medical → experience）幂等性测试。

在临时库上执行迁移核心函数，断言：数据映射正确、重复执行为 no-op、词库键迁移带备份。
不触碰真实 storage/videocut.db。
"""
import sqlite3
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate_005  # noqa: E402

OLD_TABLE_SQL = """
CREATE TABLE materials (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN ('talking_head', 'venue', 'medical', 'lesson')),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    duration REAL NOT NULL DEFAULT 0.0,
    width INTEGER NOT NULL DEFAULT 1080,
    height INTEGER NOT NULL DEFAULT 1920,
    fps REAL NOT NULL DEFAULT 30.0,
    created_at REAL NOT NULL
)
"""


def _make_db(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "mig.db"))
    conn.executescript(OLD_TABLE_SQL)
    conn.execute(
        "INSERT INTO materials VALUES ('m1','medical','a.mp4','materials/medical/a.mp4',3.0,1080,1920,30.0,0.0)"
    )
    conn.execute(
        "INSERT INTO materials VALUES ('m2','venue','b.mp4','materials/venue/b.mp4',3.0,1080,1920,30.0,0.0)"
    )
    conn.execute(
        "CREATE TABLE subtitles (id TEXT PRIMARY KEY, matched_category TEXT)"
    )
    conn.execute("INSERT INTO subtitles VALUES ('s1','medical')")
    conn.execute("INSERT INTO subtitles VALUES ('s2','venue')")
    conn.commit()
    return conn


def test_migration_maps_and_idempotent(tmp_path):
    conn = _make_db(tmp_path)
    try:
        # 首次迁移：medical 行映射为 experience，venue 不受影响
        actions = migrate_005.migrate_db(conn, apply=True)
        conn.commit()
        assert any("materials 表重建" in a for a in actions)
        rows = {r[0]: r[1] for r in conn.execute("SELECT id, category FROM materials")}
        assert rows["m1"] == "experience"
        assert rows["m2"] == "venue"
        subs = dict(conn.execute("SELECT id, matched_category FROM subtitles"))
        assert subs["s1"] == "experience" and subs["s2"] == "venue"

        # 第二次执行：全部跳过（幂等）
        actions2 = migrate_005.migrate_db(conn, apply=True)
        conn.commit()
        assert all("[跳过]" in a for a in actions2), f"重跑必须全为跳过: {actions2}"

        # 新 CHECK 约束生效：插入 medical 应被拒绝
        try:
            conn.execute(
                "INSERT INTO materials VALUES ('m3','medical','c.mp4','x.mp4',3.0,1080,1920,30.0,0.0)"
            )
            assert False, "新 CHECK 约束应拒绝 medical"
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


def test_glossary_key_migration_with_backup(tmp_path, monkeypatch):
    """词库键迁移：medical → experience，且原文件备份到 storage/legacy/"""
    import json

    glossary = tmp_path / "glossary.json"
    legacy = tmp_path / "legacy"
    glossary.write_text(
        json.dumps({"keywords": {"medical": ["体检"], "venue": ["训练场"]}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate_005, "GLOSSARY_FILE", glossary)
    monkeypatch.setattr(migrate_005, "LEGACY_DIR", legacy)

    actions = migrate_005.migrate_glossary(apply=True)
    data = json.loads(glossary.read_text(encoding="utf-8"))
    assert "experience" in data["keywords"] and "medical" not in data["keywords"]
    assert data["keywords"]["experience"] == ["体检"]
    backups = list(legacy.glob("glossary.pre-005-*.json"))
    assert len(backups) == 1, "必须自动备份原词库"

    # 幂等：无 medical 键时显示跳过
    actions2 = migrate_005.migrate_glossary(apply=True)
    assert any("[跳过]" in a for a in actions2)
