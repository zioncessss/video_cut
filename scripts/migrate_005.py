"""005 幂等迁移脚本：体检(medical) → 体验(experience) 空镜分类更名升级。

迁移内容（全部幂等，可重复执行）：
  1. SQLite materials 表 CHECK 约束重建 + category 数据 medical→experience 映射；
  2. subtitles 表 matched_category 列 medical→experience；
  3. 磁盘素材目录 storage/materials/medical → storage/materials/experience；
  4. glossary.json keywords.medical → keywords.experience（原文件自动备份至 storage/legacy/）。

惯例（对齐 scripts/apply_glossary.py）：
  - 默认试运行：仅打印将要执行的变更，不写任何数据；
  - --apply 才真正写回；
  - 后端服务运行中拒绝执行（SQLite 写冲突与内存缓存覆盖风险）。
"""
import argparse
import json
import shutil
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import DB_PATH, GLOSSARY_FILE, MATERIALS_DIR  # noqa: E402

LEGACY_DIR = ROOT_DIR / "storage" / "legacy"

# materials 表重建迁移：全部为静态字面量 SQL（SQLite 不支持 ALTER CHECK，只能重建表）
_MIGRATE_MATERIALS_SQL = """
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
       filename, filepath, duration, width, height, fps, created_at
FROM materials;
DROP TABLE materials;
ALTER TABLE materials_new RENAME TO materials;
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
"""


def backend_is_running() -> bool:
    try:
        # 固定本机健康检查地址，字面量内联，杜绝任何动态 URL 来源
        with urllib.request.urlopen("http://127.0.0.1:18888/api/health", timeout=0.6) as resp:
            return resp.status == 200
    except Exception:
        return False


def materials_table_migrated(conn: sqlite3.Connection) -> bool:
    """新 CHECK 约束（含 experience）已生效即视为已迁移"""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='materials'"
    ).fetchone()
    return bool(row and "experience" in (row[0] or ""))


def migrate_db(conn: sqlite3.Connection, apply: bool) -> list:
    actions = []
    if not materials_table_migrated(conn):
        n_med = conn.execute("SELECT COUNT(*) FROM materials WHERE category='medical'").fetchone()[0]
        actions.append(f"materials 表重建 CHECK 约束并映射 {n_med} 行 category: medical->experience")
        if apply:
            conn.execute("PRAGMA foreign_keys=off")
            conn.executescript(_MIGRATE_MATERIALS_SQL)
            conn.execute("PRAGMA foreign_keys=on")
    else:
        actions.append("[跳过] materials 表 CHECK 已含 experience，无需重建")

    n_sub = conn.execute("SELECT COUNT(*) FROM subtitles WHERE matched_category='medical'").fetchone()[0]
    if n_sub:
        actions.append(f"subtitles 表更新 {n_sub} 行 matched_category: medical->experience")
        if apply:
            conn.execute("UPDATE subtitles SET matched_category='experience' WHERE matched_category='medical'")
    else:
        actions.append("[跳过] subtitles 表无 medical 残留")
    return actions


def migrate_dirs(apply: bool) -> list:
    actions = []
    src = MATERIALS_DIR / "medical"
    dst = MATERIALS_DIR / "experience"
    if src.exists() and not dst.exists():
        actions.append(f"磁盘素材目录改名: {src} -> {dst}")
        if apply:
            src.rename(dst)
    elif src.exists() and dst.exists():
        files = list(src.glob("*"))
        actions.append(f"两目录并存，合并 {len(files)} 个文件: {src} -> {dst}")
        if apply:
            for f in files:
                target = dst / f.name
                if not target.exists():
                    shutil.move(str(f), str(target))
            src.rmdir()
    else:
        actions.append("[跳过] 磁盘目录已迁移或无旧目录")
    return actions


def migrate_glossary(apply: bool) -> list:
    actions = []
    if not GLOSSARY_FILE.exists():
        return ["[跳过] glossary.json 不存在"]
    data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
    kws = data.get("keywords") or {}
    if "medical" not in kws:
        return ["[跳过] glossary.json 无 keywords.medical 键"]
    actions.append("glossary.json keywords.medical -> keywords.experience（原文件备份至 storage/legacy/）")
    if apply:
        LEGACY_DIR.mkdir(parents=True, exist_ok=True)
        backup = LEGACY_DIR / f"glossary.pre-005-{int(time.time())}.json"
        shutil.copyfile(GLOSSARY_FILE, backup)
        kws["experience"] = kws.pop("medical")
        GLOSSARY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        actions.append(f"  已备份原词库至 {backup.name}")
    return actions


def main():
    parser = argparse.ArgumentParser(description="005: medical→experience 分类迁移（默认试运行）")
    parser.add_argument("--apply", action="store_true", help="真正写回（默认仅试运行打印变更）")
    args = parser.parse_args()

    if backend_is_running():
        print("❌ 检测到后端服务正在运行（127.0.0.1:18888），为避免 SQLite 写冲突与内存缓存覆盖，请先停止后端再执行迁移。")
        sys.exit(2)

    print(f"== 005 迁移（medical → experience）模式: {'【APPLY 实际写回】' if args.apply else '【试运行，不加 --apply 不写数据】'}==\n")

    all_actions: list = []
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    try:
        all_actions += migrate_db(conn, args.apply)
        if args.apply:
            conn.commit()
    finally:
        conn.close()
    all_actions += migrate_dirs(args.apply)
    all_actions += migrate_glossary(args.apply)

    for a in all_actions:
        print(" •", a)
    print("\n完成。再次运行本脚本应全部显示 [跳过]（幂等）。")


if __name__ == "__main__":
    main()
