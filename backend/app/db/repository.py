import json
import time
from typing import List, Optional, Dict, Any
from app.db.session import get_db_connection
from app.models.entities import (
    Material,
    MaterialCategory,
    CutProject,
    CutProjectStatus,
    SubtitleSegment,
    BrollReplacement,
    EditingStrategy,
    HighlightWord,
    SceneDecision,
    BatchJob,
    BatchJobItem,
    BatchJobStatus
)

class MaterialRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, material: Material) -> Material:
        with get_db_connection(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO materials 
                (id, category, filename, filepath, duration, width, height, fps, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                material.id,
                material.category.value if hasattr(material.category, 'value') else str(material.category),
                material.filename,
                material.filepath,
                material.duration,
                material.width,
                material.height,
                material.fps,
                material.created_at
            ))
        return material

    def get_by_id(self, material_id: str) -> Optional[Material]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,))
            row = cur.fetchone()
            if row:
                return Material(**dict(row))
        return None

    def list_all(self, category: Optional[MaterialCategory] = None) -> List[Material]:
        with get_db_connection(self.db_path) as conn:
            if category:
                cat_val = category.value if hasattr(category, 'value') else str(category)
                cur = conn.execute("SELECT * FROM materials WHERE category = ? ORDER BY created_at DESC", (cat_val,))
            else:
                cur = conn.execute("SELECT * FROM materials ORDER BY created_at DESC")
            return [Material(**dict(r)) for r in cur.fetchall()]

    def delete(self, material_id: str) -> bool:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
            return cur.rowcount > 0


class ProjectRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, project: CutProject) -> CutProject:
        project.updated_at = time.time()
        raw_asr_json = json.dumps(project.raw_asr_segments, ensure_ascii=False) if project.raw_asr_segments else None
        corrections_json = json.dumps(
            [
                (c.model_dump() if hasattr(c, "model_dump") else c)
                for c in project.corrections_summary
            ],
            ensure_ascii=False,
        ) if project.corrections_summary else None
        brolls_json = json.dumps(
            [b.model_dump() for b in project.broll_replacements], ensure_ascii=False
        ) if project.broll_replacements else None

        with get_db_connection(self.db_path) as conn:
            # 0. 确保同一素材只保留最新唯一权威工程，清理同素材的其他历史记录
            conn.execute("DELETE FROM projects WHERE talking_head_id = ? AND id != ?", (project.talking_head_id, project.id))

            # 1. 保存/更新 Project 主表（含 AI 纠偏元数据与分镜时间线）
            conn.execute("""
                INSERT OR REPLACE INTO projects
                (id, title, talking_head_id, aspect_ratio, status, output_video_path, raw_asr_json,
                 last_engine_used, corrections_summary_json, correction_latency_ms, brolls_json,
                 task_dir, cover_image_path, cover_source,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                project.title,
                project.talking_head_id,
                project.aspect_ratio,
                project.status.value if hasattr(project.status, 'value') else str(project.status),
                project.output_video_path,
                raw_asr_json,
                project.last_engine_used,
                corrections_json,
                project.correction_latency_ms,
                brolls_json,
                getattr(project, 'task_dir', None),
                getattr(project, 'cover_image_path', None),
                getattr(project, 'cover_source', None),
                project.created_at,
                project.updated_at
            ))

            # 2. 保存/更新 Subtitles（含高亮词与分镜决策）
            conn.execute("DELETE FROM subtitles WHERE project_id = ?", (project.id,))
            for idx, s in enumerate(project.subtitles):
                kw_json = json.dumps(s.matched_keywords, ensure_ascii=False) if s.matched_keywords else '[]'
                hw_json = json.dumps(
                    [w.model_dump() if hasattr(w, 'model_dump') else w for w in (s.highlight_words or [])],
                    ensure_ascii=False
                ) if s.highlight_words else '[]'
                sd_json = json.dumps(s.scene_decision.model_dump(), ensure_ascii=False) if s.scene_decision else None
                cat_val = s.matched_category.value if (s.matched_category and hasattr(s.matched_category, 'value')) else (str(s.matched_category) if s.matched_category else None)
                conn.execute("""
                    INSERT INTO subtitles
                    (id, project_id, sort_index, start_time, end_time, raw_text, corrected_text, matched_category,
                     matched_keywords_json, broll_material_id, highlight_words_json, scene_decision_json, is_manual_edited)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.id,
                    project.id,
                    idx,
                    s.start_time,
                    s.end_time,
                    s.raw_text,
                    s.corrected_text,
                    cat_val,
                    kw_json,
                    s.broll_material_id,
                    hw_json,
                    sd_json,
                    1 if s.is_manual_edited else 0
                ))

            # 3. 保存/更新 Strategy
            strat = project.strategy
            words_json = json.dumps(strat.custom_highlight_words, ensure_ascii=False) if strat.custom_highlight_words else '[]'
            conn.execute("""
                INSERT OR REPLACE INTO strategies
                (project_id, subtitle_theme, font_size, subtitle_font_size, show_subtitles, subtitle_position_y, subtitle_position_x, subtitle_width_percent,
                 enable_highlight, highlight_color, highlight_scale, custom_highlight_words_json,
                 enable_top_banner, banner_main_title, banner_sub_title, banner_style, banner_size, banner_font_size, banner_width_percent, banner_position_x, banner_position_y,
                 enable_watermark, watermark_text, watermark_position, watermark_size, watermark_font_size, watermark_position_x, watermark_position_y, watermark_opacity, broll_pacing)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project.id,
                strat.subtitle_theme,
                strat.font_size,
                getattr(strat, 'subtitle_font_size', None),
                1 if getattr(strat, 'show_subtitles', True) else 0,
                getattr(strat, 'subtitle_position_y', 82),
                getattr(strat, 'subtitle_position_x', 50),
                getattr(strat, 'subtitle_width_percent', None),
                1 if strat.enable_highlight else 0,
                strat.highlight_color,
                1 if strat.highlight_scale else 0,
                words_json,
                1 if strat.enable_top_banner else 0,
                strat.banner_main_title,
                strat.banner_sub_title,
                strat.banner_style,
                getattr(strat, 'banner_size', 'medium'),
                getattr(strat, 'banner_font_size', None),
                getattr(strat, 'banner_width_percent', None),
                getattr(strat, 'banner_position_x', 50),
                getattr(strat, 'banner_position_y', 6),
                1 if strat.enable_watermark else 0,
                strat.watermark_text,
                strat.watermark_position,
                getattr(strat, 'watermark_size', 'medium'),
                getattr(strat, 'watermark_font_size', None),
                getattr(strat, 'watermark_position_x', None),
                getattr(strat, 'watermark_position_y', None),
                strat.watermark_opacity,
                strat.broll_pacing
            ))

        return project

    def _assemble_project(self, row, conn) -> CutProject:
        project_id = row["id"]
        
        # 加载 subtitles
        cur_subs = conn.execute("SELECT * FROM subtitles WHERE project_id = ? ORDER BY sort_index ASC", (project_id,))
        subtitles: List[SubtitleSegment] = []
        broll_cuts: List[BrollReplacement] = []

        for sub_row in cur_subs.fetchall():
            kw_list = []
            try:
                kw_list = json.loads(sub_row["matched_keywords_json"] or "[]")
            except Exception:
                pass
            highlight_words = []
            try:
                raw_hw = json.loads(sub_row["highlight_words_json"] or "[]") if "highlight_words_json" in sub_row.keys() else []
                highlight_words = [HighlightWord(**w) for w in raw_hw if isinstance(w, dict) and w.get("word")]
            except Exception:
                highlight_words = []
            scene_decision = None
            try:
                raw_sd = json.loads(sub_row["scene_decision_json"]) if ("scene_decision_json" in sub_row.keys() and sub_row["scene_decision_json"]) else None
                if raw_sd:
                    scene_decision = SceneDecision(**raw_sd)
            except Exception:
                scene_decision = None

            cat_val = sub_row["matched_category"]
            cat_enum = MaterialCategory(cat_val) if cat_val else None

            seg = SubtitleSegment(
                id=sub_row["id"],
                start_time=sub_row["start_time"],
                end_time=sub_row["end_time"],
                raw_text=sub_row["raw_text"],
                corrected_text=sub_row["corrected_text"],
                matched_category=cat_enum,
                matched_keywords=kw_list,
                highlight_words=highlight_words,
                scene_decision=scene_decision,
                broll_material_id=sub_row["broll_material_id"],
                is_manual_edited=bool(sub_row["is_manual_edited"])
            )
            subtitles.append(seg)

        # 加载 strategy
        cur_strat = conn.execute("SELECT * FROM strategies WHERE project_id = ?", (project_id,))
        strat_row = cur_strat.fetchone()
        if strat_row:
            try:
                c_words = json.loads(strat_row["custom_highlight_words_json"] or "[]")
            except Exception:
                c_words = []
            keys = strat_row.keys()
            strat = EditingStrategy(
                subtitle_theme=strat_row["subtitle_theme"],
                font_size=strat_row["font_size"],
                subtitle_font_size=strat_row["subtitle_font_size"] if "subtitle_font_size" in keys else None,
                show_subtitles=bool(strat_row["show_subtitles"]),
                subtitle_position_y=strat_row["subtitle_position_y"],
                subtitle_position_x=strat_row["subtitle_position_x"],
                subtitle_width_percent=strat_row["subtitle_width_percent"] if "subtitle_width_percent" in keys else None,
                enable_highlight=bool(strat_row["enable_highlight"]),
                highlight_color=strat_row["highlight_color"],
                highlight_scale=bool(strat_row["highlight_scale"]),
                custom_highlight_words=c_words,
                enable_top_banner=bool(strat_row["enable_top_banner"]),
                banner_main_title=strat_row["banner_main_title"],
                banner_sub_title=strat_row["banner_sub_title"] or "",
                banner_style=strat_row["banner_style"],
                banner_size=strat_row["banner_size"] if "banner_size" in keys else "medium",
                banner_font_size=strat_row["banner_font_size"] if "banner_font_size" in keys else None,
                banner_width_percent=strat_row["banner_width_percent"] if "banner_width_percent" in keys else None,
                banner_position_x=strat_row["banner_position_x"] if "banner_position_x" in keys else 50,
                banner_position_y=strat_row["banner_position_y"] if "banner_position_y" in keys else 6,
                enable_watermark=bool(strat_row["enable_watermark"]),
                watermark_text=strat_row["watermark_text"],
                watermark_position=strat_row["watermark_position"],
                watermark_size=strat_row["watermark_size"] if "watermark_size" in keys else "medium",
                watermark_font_size=strat_row["watermark_font_size"] if "watermark_font_size" in keys else None,
                watermark_position_x=strat_row["watermark_position_x"] if "watermark_position_x" in keys else None,
                watermark_position_y=strat_row["watermark_position_y"] if "watermark_position_y" in keys else None,
                watermark_opacity=strat_row["watermark_opacity"],
                broll_pacing=strat_row["broll_pacing"]
            )
        else:
            strat = EditingStrategy()

        raw_asr = None
        if row["raw_asr_json"]:
            try:
                raw_asr = json.loads(row["raw_asr_json"])
            except Exception:
                pass

        # 分镜时间线：优先从 brolls_json 完整还原（含 id/playback_mode/编排后的时间窗），
        # 旧库无该列数据时回退按字幕派生（保留兼容）
        broll_cuts: List[BrollReplacement] = []
        keys = row.keys()
        if "brolls_json" in keys and row["brolls_json"]:
            try:
                for b in json.loads(row["brolls_json"]):
                    broll_cuts.append(BrollReplacement(**b))
            except Exception:
                broll_cuts = []
        if not broll_cuts:
            for seg in subtitles:
                if seg.broll_material_id:
                    broll_cuts.append(BrollReplacement(
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        material_id=seg.broll_material_id,
                        material_category=seg.matched_category
                    ))

        corrections_summary = None
        if "corrections_summary_json" in keys and row["corrections_summary_json"]:
            try:
                corrections_summary = json.loads(row["corrections_summary_json"])
            except Exception:
                corrections_summary = None

        return CutProject(
            id=row["id"],
            title=row["title"],
            talking_head_id=row["talking_head_id"],
            aspect_ratio=row["aspect_ratio"],
            status=CutProjectStatus(row["status"]),
            output_video_path=row["output_video_path"],
            task_dir=row["task_dir"] if "task_dir" in keys else None,
            cover_image_path=row["cover_image_path"] if "cover_image_path" in keys else None,
            cover_source=row["cover_source"] if "cover_source" in keys else None,
            raw_asr_segments=raw_asr,
            subtitles=subtitles,
            broll_replacements=broll_cuts,
            strategy=strat,
            corrections_summary=corrections_summary,
            last_engine_used=row["last_engine_used"] if "last_engine_used" in keys else None,
            correction_latency_ms=row["correction_latency_ms"] if "correction_latency_ms" in keys and row["correction_latency_ms"] is not None else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def get_by_id(self, project_id: str) -> Optional[CutProject]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cur.fetchone()
            if row:
                return self._assemble_project(row, conn)
        return None

    def get_by_material_id(self, talking_head_id: str) -> Optional[CutProject]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM projects WHERE talking_head_id = ? ORDER BY updated_at DESC", (talking_head_id,))
            row = cur.fetchone()
            if row:
                return self._assemble_project(row, conn)
        return None

    def delete_by_material(self, talking_head_id: str) -> bool:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("DELETE FROM projects WHERE talking_head_id = ?", (talking_head_id,))
            return cur.rowcount > 0

    def delete(self, project_id: str) -> bool:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cur.rowcount > 0

    def list_all(self) -> List[CutProject]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [self._assemble_project(r, conn) for r in cur.fetchall()]


class SettingsRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                return row["value"]
        return default

    def get_all(self) -> Dict[str, str]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT key, value FROM settings")
            return {r["key"]: r["value"] for r in cur.fetchall()}

    def set(self, key: str, value: str):
        with get_db_connection(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, time.time()))

    def set_many(self, data: Dict[str, str]):
        now = time.time()
        with get_db_connection(self.db_path) as conn:
            for k, v in data.items():
                conn.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (k, v, now))


class BatchJobRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path

    def save(self, job: BatchJob) -> BatchJob:
        with get_db_connection(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO batch_jobs (id, total_count, completed_count, concurrency, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.total_count,
                job.completed_count,
                job.concurrency,
                job.status.value if hasattr(job.status, 'value') else str(job.status),
                json.dumps([i.model_dump() for i in job.items], ensure_ascii=False) if job.items else None,
                job.created_at
            ))
        return job

    def _row_to_job(self, row) -> BatchJob:
        items = []
        if row["payload_json"]:
            try:
                items = [BatchJobItem(**i) for i in json.loads(row["payload_json"])]
            except Exception:
                items = []
        return BatchJob(
            id=row["id"],
            total_count=row["total_count"],
            completed_count=row["completed_count"],
            concurrency=row["concurrency"],
            status=BatchJobStatus(row["status"]),
            items=items,
            created_at=row["created_at"]
        )

    def get_by_id(self, job_id: str) -> Optional[BatchJob]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_job(row)
        return None

    def list_all(self) -> List[BatchJob]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM batch_jobs ORDER BY created_at DESC")
            return [self._row_to_job(r) for r in cur.fetchall()]
