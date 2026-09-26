import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional
from app.core.config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_EMBEDDED_SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN ('talking_head', 'venue', 'experience', 'lesson')),
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    duration REAL NOT NULL DEFAULT 0.0,
    width INTEGER NOT NULL DEFAULT 1080,
    height INTEGER NOT NULL DEFAULT 1920,
    fps REAL NOT NULL DEFAULT 30.0,
    content_hash TEXT DEFAULT NULL,
    file_size INTEGER DEFAULT 0,
    plate_region TEXT DEFAULT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_materials_hash ON materials(content_hash);
CREATE INDEX IF NOT EXISTS idx_materials_cat_region ON materials(category, plate_region);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    talking_head_id TEXT NOT NULL,
    target_region TEXT DEFAULT NULL,
    aspect_ratio TEXT NOT NULL DEFAULT '9:16',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'processing', 'completed', 'failed')),
    output_video_path TEXT,
    raw_asr_json TEXT,
    last_engine_used TEXT DEFAULT NULL,
    corrections_summary_json TEXT DEFAULT NULL,
    correction_latency_ms REAL DEFAULT NULL,
    brolls_json TEXT DEFAULT NULL,
    task_dir TEXT DEFAULT NULL,
    cover_image_path TEXT DEFAULT NULL,
    cover_source TEXT DEFAULT NULL,
    prune_spans_json TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_th ON projects(talking_head_id);

CREATE TABLE IF NOT EXISTS subtitles (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sort_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    raw_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    matched_category TEXT,
    matched_keywords_json TEXT DEFAULT '[]',
    broll_material_id TEXT,
    highlight_words_json TEXT DEFAULT '[]',
    scene_decision_json TEXT DEFAULT NULL,
    is_manual_edited INTEGER NOT NULL DEFAULT 0,
    is_pruned INTEGER NOT NULL DEFAULT 0,
    prune_reason TEXT DEFAULT NULL,
    prune_span_id TEXT DEFAULT NULL,
    words_json TEXT DEFAULT '[]',
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_subtitles_project ON subtitles(project_id, sort_index);

CREATE TABLE IF NOT EXISTS strategies (
    project_id TEXT PRIMARY KEY,
    subtitle_theme TEXT NOT NULL DEFAULT 'glow_gold',
    font_size TEXT NOT NULL DEFAULT 'medium',
    subtitle_font_family TEXT NOT NULL DEFAULT 'notoserif',
    subtitle_font_size INTEGER,
    show_subtitles INTEGER NOT NULL DEFAULT 1,
    subtitle_position_y INTEGER NOT NULL DEFAULT 74,
    subtitle_position_x INTEGER NOT NULL DEFAULT 50,
    video_speed REAL NOT NULL DEFAULT 1.0,
    enable_highlight INTEGER NOT NULL DEFAULT 1,
    highlight_color TEXT NOT NULL DEFAULT '#FACC15',
    highlight_scale INTEGER NOT NULL DEFAULT 1,
    custom_highlight_words_json TEXT DEFAULT '[]',
    enable_top_banner INTEGER NOT NULL DEFAULT 0,
    banner_main_title TEXT NOT NULL DEFAULT '',
    banner_sub_title TEXT DEFAULT '',
    banner_style TEXT NOT NULL DEFAULT 'capsule',
    banner_size TEXT NOT NULL DEFAULT 'medium',
    banner_font_size INTEGER,
    banner_position_x INTEGER NOT NULL DEFAULT 50,
    banner_position_y INTEGER NOT NULL DEFAULT 6,
    enable_watermark INTEGER NOT NULL DEFAULT 0,
    watermark_text TEXT NOT NULL DEFAULT '',
    watermark_position TEXT NOT NULL DEFAULT 'top_right',
    watermark_size TEXT NOT NULL DEFAULT 'medium',
    watermark_font_size INTEGER,
    watermark_position_x INTEGER,
    watermark_position_y INTEGER DEFAULT 4,
    watermark_opacity REAL NOT NULL DEFAULT 0.45,
    broll_pacing TEXT NOT NULL DEFAULT 'standard',
    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    total_count INTEGER NOT NULL,
    completed_count INTEGER NOT NULL DEFAULT 0,
    concurrency INTEGER NOT NULL DEFAULT 2,
    status TEXT NOT NULL DEFAULT 'queued',
    payload_json TEXT,
    created_at REAL NOT NULL
);
"""


def get_schema_sql() -> str:
    """获取建表 SQL：文件优先，PyInstaller 打包与代码内嵌双重兜底保证"""
    candidates = [
        SCHEMA_PATH,
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "app" / "db" / "schema.sql")
        candidates.append(Path(sys._MEIPASS) / "schema.sql")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "app" / "db" / "schema.sql")
        candidates.append(exe_dir / "_internal" / "app" / "db" / "schema.sql")
    for cand in candidates:
        if cand.exists():
            try:
                return cand.read_text(encoding="utf-8")
            except Exception:
                pass
    return _EMBEDDED_SCHEMA_SQL


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
        conn.execute("ALTER TABLE projects ADD COLUMN cover_config_json TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN suggested_cover_titles_json TEXT DEFAULT '[]';")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE strategies ADD COLUMN embed_cover_as_first_frame INTEGER NOT NULL DEFAULT 0;")
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
    try:
        conn.execute("ALTER TABLE materials ADD COLUMN plate_region TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN target_region TEXT DEFAULT NULL;")
    except Exception:
        pass
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_materials_cat_region ON materials(category, plate_region);")
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
        sql = get_schema_sql()
        if sql:
            conn.executescript(sql)
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
        sql = get_schema_sql()
        if sql:
            conn.executescript(sql)
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
