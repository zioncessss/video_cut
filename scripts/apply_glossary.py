"""
词库批量纠偏维护脚本（唯一映射源：storage/glossary.json 的 common_corrections）

用途：修改词库后，把既定纠偏映射批量应用到存量数据（历史工程），同步修正两处存储：
  1. SQLite（storage/videocut.db）：subtitles.corrected_text、strategies 横幅/水印文案
  2. 磁盘 JSON（storage/projects/*.json）：subtitles[].corrected_text、strategy 同名字段

边界（与真实执行准则一致）：
  - raw_text / raw_asr_segments / raw_asr_json 属 ASR 真实原始识别结果，一律不改
  - corrections_summary 是历史纠偏流水记录，保持原样

用法：
  python scripts/apply_glossary.py             # 试运行：仅打印将发生的变更，不写任何数据
  python scripts/apply_glossary.py --apply     # 实际写回（写前自动备份到 storage/backups/<时间戳>/）

安全约束：
  - 检测到后端服务运行中会拒绝执行（后端内存缓存会把外部改动覆盖回去），除非 --force
  - SQL 全部为 execute 调用处的字面量语句、数据经 ? 参数绑定传入；写路径强制校验位于 storage 目录内
"""
import argparse
import json
import shutil
import socket
import sqlite3
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import (  # noqa: E402
    SERVER_HOST,
    SERVER_PORT,
    STORAGE_DIR,
    apply_glossary_corrections,
    load_glossary,
)

DB_PATH = STORAGE_DIR / "videocut.db"
PROJECTS_DIR = STORAGE_DIR / "projects"
BACKUP_DIR = STORAGE_DIR / "backups"

# JSON 工程中允许词库纠偏的文本字段（raw_* 字段一律不动）
SUBTITLE_TEXT_FIELD = "corrected_text"
STRATEGY_TEXT_FIELDS = ["banner_main_title", "banner_sub_title", "watermark_text"]

# SQLite 允许纠偏的目标种类（与下方扫描/更新语句一一对应）
KIND_SUBTITLE_CORRECTED = "subtitles.corrected_text"
KIND_BANNER_MAIN = "strategies.banner_main_title"
KIND_BANNER_SUB = "strategies.banner_sub_title"
KIND_WATERMARK = "strategies.watermark_text"


def ensure_storage_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved != STORAGE_DIR.resolve() and STORAGE_DIR.resolve() not in resolved.parents:
        raise ValueError(f"路径越界，仅允许访问 {STORAGE_DIR} 目录内的文件: {path}")
    return resolved


def backend_is_running(timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=timeout):
            return True
    except OSError:
        return False


def backup(paths, stamp: str):
    target_dir = ensure_storage_path(BACKUP_DIR / stamp)
    target_dir.mkdir(parents=True, exist_ok=True)
    for p in paths:
        if p.exists():
            dest = target_dir / p.name
            shutil.copy2(p, dest)
            print(f"  [备份] {p.name} -> {dest}")
    return target_dir


def scan_db_changes(conn):
    """扫描 SQLite 各目标列，返回 (种类, 主键值, 旧文本, 新文本) 列表（不写入）"""
    changes = []
    rows = conn.execute("SELECT id, corrected_text FROM subtitles").fetchall()
    for row_id, text in rows:
        if not text:
            continue
        new_text, _ = apply_glossary_corrections(str(text))
        if new_text != text:
            changes.append((KIND_SUBTITLE_CORRECTED, row_id, text, new_text))

    rows = conn.execute("SELECT project_id, banner_main_title FROM strategies").fetchall()
    for row_id, text in rows:
        if not text:
            continue
        new_text, _ = apply_glossary_corrections(str(text))
        if new_text != text:
            changes.append((KIND_BANNER_MAIN, row_id, text, new_text))

    rows = conn.execute("SELECT project_id, banner_sub_title FROM strategies").fetchall()
    for row_id, text in rows:
        if not text:
            continue
        new_text, _ = apply_glossary_corrections(str(text))
        if new_text != text:
            changes.append((KIND_BANNER_SUB, row_id, text, new_text))

    rows = conn.execute("SELECT project_id, watermark_text FROM strategies").fetchall()
    for row_id, text in rows:
        if not text:
            continue
        new_text, _ = apply_glossary_corrections(str(text))
        if new_text != text:
            changes.append((KIND_WATERMARK, row_id, text, new_text))
    return changes


def update_db_changes(conn, changes):
    for kind, row_id, _old, new in changes:
        if kind == KIND_SUBTITLE_CORRECTED:
            conn.execute("UPDATE subtitles SET corrected_text = ? WHERE id = ?", (new, row_id))
        elif kind == KIND_BANNER_MAIN:
            conn.execute("UPDATE strategies SET banner_main_title = ? WHERE project_id = ?", (new, row_id))
        elif kind == KIND_BANNER_SUB:
            conn.execute("UPDATE strategies SET banner_sub_title = ? WHERE project_id = ?", (new, row_id))
        elif kind == KIND_WATERMARK:
            conn.execute("UPDATE strategies SET watermark_text = ? WHERE project_id = ?", (new, row_id))
    conn.commit()


def collect_changes():
    """扫描 SQLite 与工程 JSON，汇总词库纠偏将产生的全部变更（不写入）"""
    conn = sqlite3.connect(DB_PATH)
    try:
        db_changes = scan_db_changes(conn)
    finally:
        conn.close()

    json_changes = []  # (文件, 位置描述, 旧文本, 新文本)
    for json_file in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [跳过] {json_file.name} 解析失败: {e}")
            continue
        for i, seg in enumerate(data.get("subtitles") or []):
            old = seg.get(SUBTITLE_TEXT_FIELD)
            if not old:
                continue
            new, _ = apply_glossary_corrections(str(old))
            if new != old:
                json_changes.append((json_file, f"subtitles[{i}].{SUBTITLE_TEXT_FIELD}", old, new))
        strategy = data.get("strategy") or {}
        for field in STRATEGY_TEXT_FIELDS:
            old = strategy.get(field)
            if not old:
                continue
            new, _ = apply_glossary_corrections(str(old))
            if new != old:
                json_changes.append((json_file, f"strategy.{field}", old, new))
    return db_changes, json_changes


def apply_json_changes(json_changes):
    by_file = {}
    for json_file, location, old, new in json_changes:
        by_file.setdefault(json_file, []).append((location, old, new))
    for json_file, changes in by_file.items():
        data = json.loads(json_file.read_text(encoding="utf-8"))
        for location, _old, new in changes:
            keys = location.split(".")
            if keys[0] == "strategy":
                data["strategy"][keys[1]] = new
            else:
                # 形如 subtitles[3].corrected_text
                index = int(keys[0][len("subtitles["):-1])
                data["subtitles"][index][keys[1]] = new
        json_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def main():
    parser = argparse.ArgumentParser(description="按 storage/glossary.json 词库批量纠偏存量工程数据")
    parser.add_argument("--apply", action="store_true", help="实际写回（默认仅试运行打印变更）")
    parser.add_argument("--force", action="store_true", help="忽略后端运行中检测（不推荐）")
    args = parser.parse_args()

    glossary = load_glossary()
    corrections = glossary.get("common_corrections") or {}
    if not corrections:
        print("词库 common_corrections 为空，无映射可应用。请先编辑 storage/glossary.json")
        return

    print(f"词库映射共 {len(corrections)} 条（长词优先应用）。")

    if backend_is_running():
        if not args.force:
            print(f"拒绝执行：后端服务 {SERVER_HOST}:{SERVER_PORT} 正在运行，其内存缓存会覆盖本脚本的修改。")
            print("请先停止后端，或确认后使用 --force。")
            sys.exit(2)
        print("警告：后端正在运行且已指定 --force，改动可能被后端内存缓存覆盖！")

    db_changes, json_changes = collect_changes()

    if not db_changes and not json_changes:
        print("扫描完成：SQLite 与全部工程 JSON 均已符合词库，无需纠偏。")
        return

    print(f"\n将发生 {len(db_changes)} 处 SQLite 变更、{len(json_changes)} 处 JSON 变更：")
    for kind, row_id, old, new in db_changes:
        print(f"  [{kind}] {row_id}: {old!r} -> {new!r}")
    for json_file, location, old, new in json_changes:
        print(f"  [{json_file.name} {location}] {old!r} -> {new!r}")

    if not args.apply:
        print("\n以上为试运行结果（未写入）。确认无误后追加 --apply 执行。")
        return

    stamp = time.strftime("%Y%m%d_%H%M%S")
    print("\n写回前自动备份：")
    backup([DB_PATH] + sorted(PROJECTS_DIR.glob("*.json")), stamp)
    conn = sqlite3.connect(DB_PATH)
    try:
        update_db_changes(conn, db_changes)
    finally:
        conn.close()
    apply_json_changes(json_changes)
    print(f"\n完成：SQLite {len(db_changes)} 处、JSON {len(json_changes)} 处已按词库纠偏。备份目录：{BACKUP_DIR / stamp}")


if __name__ == "__main__":
    main()
