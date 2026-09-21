-- SQLite Schema for VideoCut Desktop Application

PRAGMA foreign_keys = ON;

-- 素材元数据表（experience 为原 medical 的更名升级，旧库由 scripts/migrate_005.py 平滑迁移）
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
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_materials_category ON materials(category);
CREATE INDEX IF NOT EXISTS idx_materials_hash ON materials(content_hash);

-- 剪辑工程元数据表
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    talking_head_id TEXT NOT NULL,
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

-- 字幕片段与语义空镜映射表
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

-- 剪辑策略工坊参数表
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

-- 全局设置表
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

-- 批量混剪作业队列表（payload_json 逐项状态，005 新增）
CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    total_count INTEGER NOT NULL,
    completed_count INTEGER NOT NULL DEFAULT 0,
    concurrency INTEGER NOT NULL DEFAULT 2,
    status TEXT NOT NULL DEFAULT 'queued',
    payload_json TEXT,
    created_at REAL NOT NULL
);
