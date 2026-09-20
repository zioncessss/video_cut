import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from app.core.config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _ensure_columns(conn) -> None:
    """幂等增量列自愈（init_db 与 get_db_connection 共用此唯一清单）。

    schema.sql 的运行时平滑迁移：全部为字面量 DDL，已存在的列因重复添加失败被安全忽略。
    新增列只在此登记一次，两处入口自动生效。
    """
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN banner_size TEXT NOT NULL DEFAULT 'medium';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN banner_position_y INTEGER NOT NULL DEFAULT 6;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN banner_position_x INTEGER NOT NULL DEFAULT 50;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN banner_font_size INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN banner_width_percent INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN watermark_size TEXT NOT NULL DEFAULT 'medium';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN watermark_position_y INTEGER DEFAULT 4;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN watermark_position_x INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN watermark_font_size INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN subtitle_font_size INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN font_size TEXT NOT NULL DEFAULT 'medium';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN subtitle_width_percent INTEGER DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN subtitle_font_family TEXT NOT NULL DEFAULT 'notoserif';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN video_speed REAL NOT NULL DEFAULT 1.0;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN last_engine_used TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN corrections_summary_json TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN correction_latency_ms REAL DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN brolls_json TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN highlight_words_json TEXT DEFAULT '[]';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN scene_decision_json TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE batch_jobs ADD COLUMN payload_json TEXT;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN task_dir TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN cover_image_path TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN cover_source TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN prune_spans_json TEXT DEFAULT '[]';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN is_pruned INTEGER NOT NULL DEFAULT 0;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN prune_reason TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN prune_span_id TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE subtitles ADD COLUMN words_json TEXT DEFAULT '[]';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE materials ADD COLUMN content_hash TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE materials ADD COLUMN file_size INTEGER DEFAULT 0;")
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_materials_hash ON materials(content_hash);")
    except Exception:
        pass
    # 历史硬编码水印文案与无字开启状态自愈清洗（未填文字绝不默认开启或保存文案）
    try:
        conn.execute("""
            UPDATE strategies 
            SET enable_watermark = 0, watermark_text = '' 
            WHERE watermark_text = '@顺达驾校官方教学' 
               OR watermark_text IS NULL 
               OR trim(watermark_text) = '';
        """)
    except Exception:
        pass
    conn.commit()


def init_db(db_path: Optional[Path] = None):
    """初始化数据库并应用 schema.sql 与增量列自愈"""
    target_path = db_path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(target_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        _ensure_columns(conn)

@contextmanager
def get_db_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """获取配置好 WAL 模式与外键约束的 SQLite 连接"""
    target_path = db_path or DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    # 防御性自愈：如果数据库未建表（如单测独立调用场景），自动应用 schema；
    # 已建表则同样应用共享的增量列自愈清单（projects 新列等在此补齐）
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materials';")
    if not cursor.fetchone():
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        _ensure_columns(conn)
        conn.commit()
    else:
        _ensure_columns(conn)
    cursor.close()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
