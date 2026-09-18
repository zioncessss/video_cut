import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Optional
from app.core.config import STORAGE_DIR, PROJECTS_DIR, SETTINGS_FILE, MATERIALS_DIR, GLOSSARY_FILE
from app.db.session import init_db
from app.db.repository import MaterialRepository, ProjectRepository, SettingsRepository
from app.models.entities import Material, CutProject

META_FILE = STORAGE_DIR / "materials_meta.json"
LEGACY_DIR = STORAGE_DIR / "legacy"

# 005 分类迁移：materials 表重建（SQLite 不支持 ALTER CHECK），全部为静态字面量 SQL
_MIGRATE_MATERIALS_EXPERIENCE_SQL = """
CREATE TABLE materials_new (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN ('talking_head', 'venue', 'experience', 'lesson')),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    duration REAL NOT NULL DEFAULT 0.0,
    width INTEGER NOT NULL DEFAULT 1080,
    height INTEGER NOT NULL DEFAULT 1920,
    fps REAL NOT NULL DEFAULT 30.0,
    created_at REAL NOT NULL
);
INSERT INTO materials_new (id, category, filename, filepath, duration, width, height, fps, created_at)
SELECT id,
       CASE WHEN category='medical' THEN 'experience' ELSE category END,
       filename,
       CASE WHEN filepath LIKE '%/medical/%' THEN replace(filepath, '/medical/', '/experience/') ELSE filepath END,
       duration, width, height, fps, created_at
FROM materials;
DROP TABLE materials;
ALTER TABLE materials_new RENAME TO materials;
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
"""


def migrate_category_experience(db_path: Optional[Path] = None, dry_run: bool = False) -> list:
    """005 自动迁移：体检(medical) → 体验(experience) 空镜分类（幂等，可重复执行）。

    1. SQLite materials 表 CHECK 重建并映射行数据（含 filepath 目录段替换）；
    2. subtitles.matched_category 列 medical→experience；
    3. 磁盘素材目录 medical/ 并入 experience/；
    4. glossary.json keywords.medical → keywords.experience（原文件备份至 storage/legacy/）；
    5. 影子文件 materials_meta.json 同步改写（保持迁移期一致性）。
    返回执行的动作描述列表（供脚本试运行打印）。
    """
    actions: list = []
    conn = sqlite3.connect(str(db_path or _default_db_path()), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='materials'").fetchone()
        table_exists = bool(row)
        need_rebuild = table_exists and "experience" not in (row["sql"] or "")
        if not table_exists:
            actions.append("[跳过] materials 表不存在（将由 schema.sql 全新建表）")
        elif need_rebuild:
            n_med = conn.execute("SELECT COUNT(*) FROM materials WHERE category='medical'").fetchone()[0]
            actions.append(f"materials 表重建 CHECK 约束并映射 {n_med} 行 category/filepath: medical->experience")
            if not dry_run:
                conn.execute("PRAGMA foreign_keys=off")
                conn.executescript(_MIGRATE_MATERIALS_EXPERIENCE_SQL)
                conn.execute("PRAGMA foreign_keys=on")
        else:
            actions.append("[跳过] materials 表 CHECK 已含 experience")

        if table_exists:
            has_subs = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='subtitles'"
            ).fetchone()
            n_sub = 0
            if has_subs:
                n_sub = conn.execute("SELECT COUNT(*) FROM subtitles WHERE matched_category='medical'").fetchone()[0]
            if n_sub:
                actions.append(f"subtitles 表更新 {n_sub} 行 matched_category: medical->experience")
                if not dry_run:
                    conn.execute("UPDATE subtitles SET matched_category='experience' WHERE matched_category='medical'")
            else:
                actions.append("[跳过] subtitles 表无 medical 残留")
        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    # 磁盘目录：medical/ 并入 experience/
    src = MATERIALS_DIR / "medical"
    dst = MATERIALS_DIR / "experience"
    if src.exists() and not dst.exists():
        actions.append(f"磁盘素材目录改名: {src.name}/ -> {dst.name}/")
        if not dry_run:
            src.rename(dst)
    elif src.exists() and dst.exists():
        files = list(src.glob("*"))
        if files:
            actions.append(f"两目录并存，合并 {len(files)} 个文件: medical/ -> experience/")
            if not dry_run:
                for f in files:
                    target = dst / f.name
                    if not target.exists():
                        shutil.move(str(f), str(target))
                src.rmdir()
        else:
            actions.append("[跳过] medical/ 目录为空")
            if not dry_run:
                src.rmdir()
    else:
        actions.append("[跳过] 磁盘目录已迁移或无旧目录")

    # 词库键迁移（自动备份）
    if GLOSSARY_FILE.exists():
        data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
        kws = data.get("keywords") or {}
        if "medical" in kws:
            actions.append("glossary.json keywords.medical -> keywords.experience（原文件备份至 storage/legacy/）")
            if not dry_run:
                LEGACY_DIR.mkdir(parents=True, exist_ok=True)
                backup = LEGACY_DIR / f"glossary.pre-005-{int(time.time())}.json"
                shutil.copyfile(GLOSSARY_FILE, backup)
                kws["experience"] = kws.pop("medical")
                GLOSSARY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            actions.append("[跳过] glossary.json 无 keywords.medical 键")

    # 影子文件同步（迁移期 SQLite 不可用时的回退数据源，必须与权威库一致）
    if META_FILE.exists():
        try:
            meta = json.loads(META_FILE.read_text(encoding="utf-8"))
            changed = False
            for m in meta:
                if m.get("category") == "medical":
                    m["category"] = "experience"
                    m["filepath"] = str(m.get("filepath", "")).replace("/materials/medical/", "/materials/experience/")
                    changed = True
            if changed:
                actions.append("materials_meta.json 影子数据同步 medical->experience")
                if not dry_run:
                    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                actions.append("[跳过] materials_meta.json 无 medical 数据")
        except Exception as e:
            actions.append(f"[警告] materials_meta.json 同步失败: {e}")

    return actions


def _default_db_path() -> Path:
    from app.core.config import DB_PATH
    return DB_PATH

def migrate_legacy_data(db_path: Optional[Path] = None):
    """平滑升级：将旧版 materials_meta.json、projects/*.json 与 settings.json 迁移至 SQLite"""
    init_db(db_path)

    # 005 分类迁移必须先于 legacy 数据导入执行（重建 CHECK 约束，否则 medical 行无法映射入库）
    try:
        actions = migrate_category_experience(db_path)
        for a in actions:
            if not a.startswith("[跳过]"):
                print(f"[Migrator][005] {a}")
    except Exception as e:
        print(f"[Migrator][005] 分类迁移异常: {e}")

    mat_repo = MaterialRepository(db_path)
    proj_repo = ProjectRepository(db_path)
    settings_repo = SettingsRepository(db_path)

    # 0. 检查是否已完成过历史数据迁移，避免重复执行与已删除素材死灰复燃
    if settings_repo.get("legacy_data_migrated") == "1":
        return

    # 1. 迁移素材元数据（medical 分类同步映射为 experience，兼容新 CHECK 约束）
    if META_FILE.exists():
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                materials_data = json.load(f)
                for item in materials_data:
                    if item.get("category") == "medical":
                        item = dict(item)
                        item["category"] = "experience"
                        item["filepath"] = str(item.get("filepath", "")).replace("/materials/medical/", "/materials/experience/")
                    m = Material(**item)
                    if not mat_repo.get_by_id(m.id):
                        mat_repo.save(m)
        except Exception as e:
            print(f"[Migrator] 迁移 materials_meta.json 异常: {e}")

    # 2. 迁移持久化剪辑工程（孤儿工程不删除，随有效工程一并归档，零丢失）
    if PROJECTS_DIR.exists():
        for p_file in PROJECTS_DIR.glob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    proj_data = json.load(f)
                    p = CutProject(**proj_data)
                    # 严禁捏造虚假占位素材！若口播素材已被物理清理，此工程为孤儿残留，跳过导入（文件仍会归档）
                    if not mat_repo.get_by_id(p.talking_head_id):
                        print(f"[Migrator] 工程引用的口播素材不存在（孤儿残留，导入跳过）: {p_file.name}")
                        continue

                    if not proj_repo.get_by_id(p.id):
                        proj_repo.save(p)
            except Exception as e:
                print(f"[Migrator] 迁移工程文件 {p_file} 异常: {e}")

    # 3. 迁移配置数据
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
                for k, v in settings_data.items():
                    if settings_repo.get(k) is None:
                        settings_repo.set(k, str(v))
        except Exception as e:
            print(f"[Migrator] 迁移 settings.json 异常: {e}")

    # 4. 归档已迁移的 JSON 源文件到 storage/legacy/（零丢失：只移动不删除）
    def _archive_to_legacy(src: Path):
        try:
            LEGACY_DIR.mkdir(parents=True, exist_ok=True)
            dest = LEGACY_DIR / src.name
            if dest.exists():
                dest = LEGACY_DIR / f"{src.stem}_{int(time.time())}{src.suffix}"
            shutil.move(str(src), str(dest))
        except Exception as e:
            print(f"[Migrator] 归档 {src.name} 失败（保留原文件）: {e}")

    if META_FILE.exists():
        _archive_to_legacy(META_FILE)
        print("[Migrator] materials_meta.json 已归档至 storage/legacy/")
    if PROJECTS_DIR.exists():
        archived = 0
        for p_file in PROJECTS_DIR.glob("*.json"):
            _archive_to_legacy(p_file)
            archived += 1
        if archived:
            print(f"[Migrator] {archived} 个工程 JSON 已归档至 storage/legacy/")

    try:
        settings_repo.set("legacy_data_migrated", "1")
    except Exception as e:
        print(f"[Migrator] 记录迁移标记异常: {e}")
