import sys
import os
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.native_engine.asr_runner import asr_runner
from app.native_engine.keyword_matcher import build_highlight_words, match_keywords_in_segment
from app.core.config import apply_glossary_corrections, load_glossary

def refresh_project(project_id: str = None):
    db_path = Path("storage/videocut.db")
    if not db_path.exists():
        print("Database not found")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    if not project_id:
        row = c.execute("SELECT id FROM projects ORDER BY updated_at DESC LIMIT 1").fetchone()
        if not row:
            print("No project found")
            return
        project_id = row[0]

    print(f"Refreshing project: {project_id}")

    proj_row = c.execute(
        "SELECT id, raw_asr_json, brolls_json FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()

    if not proj_row:
        print("Project not found in DB")
        return

    pid, raw_asr_json, brolls_json = proj_row
    raw_segments = json.loads(raw_asr_json) if raw_asr_json else []
    brolls = json.loads(brolls_json) if brolls_json else []

    if not raw_segments:
        print("No raw ASR segments in project")
        return

    # Load existing subtitle scene decisions to preserve broll alignments
    old_subs = c.execute(
        "SELECT id, start_time, end_time, scene_decision_json, broll_material_id FROM subtitles WHERE project_id = ? ORDER BY sort_index",
        (project_id,)
    ).fetchall()
    
    old_sd_map = []
    for s_id, st, et, sd_json, bm_id in old_subs:
        sd = json.loads(sd_json) if sd_json else None
        old_sd_map.append({
            "start": st,
            "end": et,
            "scene_decision": sd,
            "broll_material_id": bm_id
        })

    # 1. 词库确定性纠偏
    candidate_subs = []
    for s in raw_segments:
        raw_t = str(s.get("raw_text") or s.get("text") or "")
        corr_t, _ = apply_glossary_corrections(raw_t)
        item = dict(s)
        item["raw_text"] = raw_t
        item["corrected_text"] = corr_t
        candidate_subs.append(item)

    # 2. 过滤语气词
    valid_clauses = asr_runner.filter_filler_segments(candidate_subs)

    # 3. 智能自然句切分（带防断词保护）
    split_segments = asr_runner.split_into_readable_segments(valid_clauses, max_chars=14, soft_max=14, min_chunk=4)

    # 4. 短句碎片平滑合并（单行上限 14 字）
    corrected_segments = asr_runner.merge_short_segments(
        split_segments,
        min_chars=4,
        min_duration=1.0,
        max_chars=14,
        max_gap=0.55,
        max_duration=3.8
    )

    print(f"Generated {len(corrected_segments)} segments (was {len(old_subs)})")

    # 5. 生成新 subtitles 记录
    new_subtitles = []
    for idx, item in enumerate(corrected_segments):
        c_text = item.get("corrected_text", "")
        kw_info = match_keywords_in_segment(c_text)
        matched_cat = kw_info.get("matched_category")
        matched_kws = kw_info.get("matched_keywords", [])

        # 高亮词规则提取
        hw_list = build_highlight_words(c_text, item.get("highlight_words"))

        # 对齐空镜和分镜决策
        mid = (float(item["start_time"]) + float(item["end_time"])) / 2.0
        assigned_sd = None
        assigned_bm_id = None
        
        # 优先在 old_sd_map 中找时间覆盖最大的
        for old_item in old_sd_map:
            if old_item["start"] <= mid <= old_item["end"]:
                assigned_sd = old_item["scene_decision"]
                assigned_bm_id = old_item["broll_material_id"]
                break
                
        # 降级在 brolls 中找
        if not assigned_bm_id:
            for b in brolls:
                b_st = float(b.get("start_time", 0.0))
                b_et = float(b.get("end_time", 0.0))
                if b_st <= mid <= b_et:
                    assigned_bm_id = b.get("material_id")
                    if not assigned_sd:
                        assigned_sd = {
                            "part": "body",
                            "broll_category": b.get("material_category"),
                            "broll_duration": round(b_et - b_st, 2),
                            "transition_seconds": 0.0,
                            "material_id": assigned_bm_id,
                            "reason": "双层黄金编排分镜"
                        }
                    break

        sub_id = f"sub_{idx:03d}_{project_id[:6]}"
        new_subtitles.append((
            sub_id,
            project_id,
            idx,
            float(item["start_time"]),
            float(item["end_time"]),
            item.get("raw_text", c_text),
            c_text,
            matched_cat,
            json.dumps(matched_kws, ensure_ascii=False),
            assigned_bm_id,
            0,
            json.dumps(hw_list, ensure_ascii=False),
            json.dumps(assigned_sd, ensure_ascii=False) if assigned_sd else None
        ))

    # 6. 更新数据库
    c.execute("DELETE FROM subtitles WHERE project_id = ?", (project_id,))
    c.executemany(
        """
        INSERT INTO subtitles (
            id, project_id, sort_index, start_time, end_time,
            raw_text, corrected_text, matched_category, matched_keywords_json,
            broll_material_id, is_manual_edited, highlight_words_json, scene_decision_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        new_subtitles
    )

    conn.commit()
    conn.close()
    print(f"Successfully refreshed {len(new_subtitles)} subtitles in DB!")

    # Verify sentence 6 and 7
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    sample = c.execute(
        "SELECT sort_index, start_time, end_time, corrected_text, highlight_words_json FROM subtitles WHERE project_id = ? ORDER BY sort_index LIMIT 15",
        (project_id,)
    ).fetchall()
    print("\n--- FIRST 15 SUBTITLES ---")
    for s_idx, st, et, txt, hw_j in sample:
        hw = json.loads(hw_j) if hw_j else []
        hw_str = ", ".join(f"{h['word']}({h.get('color')})" for h in hw) if hw else "none"
        print(f"[{s_idx:02d}] {st:.2f}s - {et:.2f}s: {txt} | hw: {hw_str}")
    conn.close()

if __name__ == "__main__":
    refresh_project()
