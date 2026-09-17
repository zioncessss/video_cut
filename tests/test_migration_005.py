"""005 分类迁移（medical → experience）幂等性测试。

覆盖两层实现：
1. migrator.migrate_category_experience（应用启动自动迁移路径）；
2. scripts/migrate_005 手动脚本对同一实现的复用。
全部在临时库/临时目录上执行，不触碰真实 storage/videocut.db。
"""
import json
import sqlite3
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate_005  # noqa: E402
from app.db import migrator  # noqa: E402

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


def test_migration_maps_and_idempotent(tmp_path, monkeypatch):
    """权威库迁移：medical 行映射为 experience（含 filepath 目录段），venue 不受影响，重跑幂等"""
    db_path = tmp_path / "mig.db"
    conn = _make_db(tmp_path)
    conn.close()

    # 磁盘环境仅词库为空文件，聚焦 DB 行为断言
    glossary = tmp_path / "glossary.json"
    glossary.write_text('{"keywords": {}}', encoding="utf-8")
    monkeypatch.setattr(migrator, "GLOSSARY_FILE", glossary)
    monkeypatch.setattr(migrator, "META_FILE", tmp_path / "materials_meta.json")

    # 首次迁移：medical 行映射为 experience，venue 不受影响
    actions = migrator.migrate_category_experience(db_path=db_path)
    assert any("materials 表重建" in a for a in actions)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = {r[0]: r[1] for r in conn.execute("SELECT id, category FROM materials")}
        assert rows["m1"] == "experience"
        assert rows["m2"] == "venue"
        # filepath 目录段同步替换
        assert conn.execute("SELECT filepath FROM materials WHERE id='m1'").fetchone()[0] == "materials/experience/a.mp4"
        subs = dict(conn.execute("SELECT id, matched_category FROM subtitles"))
        assert subs["s1"] == "experience" and subs["s2"] == "venue"

        # 第二次执行：全部跳过（幂等）
        actions2 = migrator.migrate_category_experience(db_path=db_path)
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


def test_auto_migration_in_migrator(tmp_path, monkeypatch):
    """启动链自动迁移（migrator.migrate_category_experience）：DB/目录/词库/影子文件全要素幂等迁移"""
    import json as _json

    db = tmp_path / "auto.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(OLD_TABLE_SQL)
    conn.execute(
        "INSERT INTO materials VALUES ('m1','medical','a.mp4','storage/materials/medical/a.mp4',3.0,1080,1920,30.0,0.0)"
    )
    conn.execute("CREATE TABLE subtitles (id TEXT PRIMARY KEY, matched_category TEXT)")
    conn.execute("INSERT INTO subtitles VALUES ('s1','medical')")
    conn.commit()
    conn.close()

    # 临时磁盘环境：medical 与 experience 目录并存 + 旧词库键 + 影子 meta
    mats = tmp_path / "materials"
    (mats / "medical").mkdir(parents=True)
    (mats / "experience").mkdir(parents=True)
    (mats / "medical" / "a.mp4").write_bytes(b"x")
    glossary = tmp_path / "glossary.json"
    glossary.write_text(_json.dumps({"keywords": {"medical": ["体检"]}}, ensure_ascii=False), encoding="utf-8")
    meta = tmp_path / "materials_meta.json"
    meta.write_text(_json.dumps([{"id": "m1", "category": "medical", "filepath": "storage/materials/medical/a.mp4"}]), encoding="utf-8")

    monkeypatch.setattr(migrator, "MATERIALS_DIR", mats)
    monkeypatch.setattr(migrator, "GLOSSARY_FILE", glossary)
    monkeypatch.setattr(migrator, "META_FILE", meta)
    monkeypatch.setattr(migrator, "LEGACY_DIR", tmp_path / "legacy")

    actions = migrator.migrate_category_experience(db_path=db)
    assert any("materials 表重建" in a for a in actions)

    # 权威库：行数据与文件路径全部映射，新 CHECK 拒绝 medical
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT category FROM materials WHERE id='m1'").fetchone()[0] == "experience"
    assert conn.execute("SELECT filepath FROM materials WHERE id='m1'").fetchone()[0] == "storage/materials/experience/a.mp4"
    assert conn.execute("SELECT matched_category FROM subtitles WHERE id='s1'").fetchone()[0] == "experience"
    try:
        conn.execute("INSERT INTO materials VALUES ('m9','medical','c.mp4','x.mp4',1,1,1,30.0,0.0)")
        assert False, "新 CHECK 应拒绝 medical"
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

    # 磁盘与配置落位
    assert (mats / "experience" / "a.mp4").exists()
    assert not (mats / "medical").exists()
    g = _json.loads(glossary.read_text(encoding="utf-8"))
    assert g["keywords"]["experience"] == ["体检"] and "medical" not in g["keywords"]
    assert list((tmp_path / "legacy").glob("glossary.pre-005-*.json")), "词库必须自动备份"
    m = _json.loads(meta.read_text(encoding="utf-8"))
    assert m[0]["category"] == "experience" and "/experience/" in m[0]["filepath"]

    # 幂等：重跑全部跳过
    actions2 = migrator.migrate_category_experience(db_path=db)
    assert all("[跳过]" in a for a in actions2), f"重跑必须全为跳过: {actions2}"
