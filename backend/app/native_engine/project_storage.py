import json
import re
import time
import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import PROJECTS_DIR, TASKS_DIR, STORAGE_DIR, OUTPUTS_DIR, COVERS_DIR, resolve_media_path, to_storage_relative
from app.models.entities import CutProject, CutProjectStatus, SubtitleSegment, EditingStrategy, HighlightWord
from app.native_engine.keyword_matcher import build_highlight_words
from app.db.repository import ProjectRepository

class ProjectStorageService:
    def __init__(self, storage_dir: Path = PROJECTS_DIR, db_path=None):
        self.storage_dir = storage_dir
        self.repo = ProjectRepository(db_path)
        self._cache_by_th_id: Dict[str, CutProject] = {}
        self._cache_by_proj_id: Dict[str, CutProject] = {}
        self._load_all()

    def _parse_srt(self, srt_content: str) -> List[SubtitleSegment]:
        """简易鲁棒解析 SRT 文件为字幕分段列表，并自动补充高光词"""
        segments = []
        blocks = re.split(r'\n\s*\n', srt_content.strip())
        for block in blocks:
            lines = [l.strip() for l in block.split('\n') if l.strip()]
            if len(lines) >= 3 and '-->' in lines[1]:
                time_match = re.match(r'(\d+):(\d+):(\d+)[,\.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,\.](\d+)', lines[1])
                if time_match:
                    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, time_match.groups())
                    start_sec = round(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0, 3)
                    end_sec = round(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0, 3)
                    text = " ".join(lines[2:])
                    h_words = [
                        HighlightWord(**w) for w in build_highlight_words(text)
                        if isinstance(w, dict) and w.get("word")
                    ]
                    segments.append(SubtitleSegment(
                        id=str(uuid.uuid4()),
                        start_time=start_sec,
                        end_time=end_sec,
                        raw_text=text,
                        corrected_text=text,
                        highlight_words=h_words,
                        matched_keywords=[w.word for w in h_words]
                    ))
        return segments

    def _parse_ass_subtitles(self, ass_content: str) -> List[SubtitleSegment]:
        """从 ASS 文件提取字幕时间戳、纯文本与行内高亮关键词"""
        segments = []
        lines = ass_content.splitlines()
        for line in lines:
            line = line.strip()
            if not line.startswith("Dialogue:"):
                continue
            # Format: Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
            parts = line.split(",", 9)
            if len(parts) < 10:
                continue
            st_str, et_str = parts[1].strip(), parts[2].strip()
            raw_dialogue = parts[9].strip()

            # 解析开始和结束时间 (H:MM:SS.cs)
            def parse_ass_t(t_str: str) -> float:
                p = t_str.split(":")
                if len(p) == 3:
                    return round(int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2]), 3)
                return 0.0

            st = parse_ass_t(st_str)
            et = parse_ass_t(et_str)

            # 提取 ASS 高亮标签中包裹的词与颜色
            extracted_hws: List[HighlightWord] = []
            for m in re.finditer(r'\{[^\}]*\\c&H([0-9a-fA-F]+)&[^\}]*\}([^{]+)\{\\r', raw_dialogue):
                hex_c_raw = m.group(1).upper().zfill(6)
                # ASS 色彩格式为 &HAABBGGRR 或 &HBBGGRR，换算为 #RRGGBB
                if len(hex_c_raw) >= 6:
                    bb = hex_c_raw[-6:-4]
                    gg = hex_c_raw[-4:-2]
                    rr = hex_c_raw[-2:]
                    hex_color = f"#{rr}{gg}{bb}"
                else:
                    hex_color = "#FACC15"
                word = m.group(2).strip()
                if word:
                    extracted_hws.append(HighlightWord(word=word, color=hex_color, source="ass"))

            # 纯白强调标签 {\b1\fscx122\fscy122}word{\r...}
            for m in re.finditer(r'\{[^\}]*\\fscx122[^\}]*\}([^{]+)\{\\r', raw_dialogue):
                word = m.group(1).strip()
                if word and not any(w.word == word for w in extracted_hws):
                    extracted_hws.append(HighlightWord(word=word, color="#FFFFFF", source="ass"))

            clean_text = re.sub(r'\{[^\}]*\}', '', raw_dialogue).strip()
            if not clean_text:
                continue

            # 若 ASS 中未打标签，通过规则引擎自愈补齐高亮词
            if not extracted_hws:
                extracted_hws = [
                    HighlightWord(**w) for w in build_highlight_words(clean_text)
                    if isinstance(w, dict) and w.get("word")
                ]

            segments.append(SubtitleSegment(
                id=str(uuid.uuid4()),
                start_time=st,
                end_time=et,
                raw_text=clean_text,
                corrected_text=clean_text,
                highlight_words=extracted_hws,
                matched_keywords=[w.word for w in extracted_hws]
            ))
        return segments

    def _heal_from_disk(self):
        """从磁盘自包含任务目录 (storage/tasks) 与历史工程 JSON (storage/projects) 自动自愈恢复未入库工程"""
        # 查询所有合法存在的素材 ID，强校验素材存在性
        valid_mat_ids = set()
        try:
            from app.db.session import get_db_connection
            with get_db_connection(self.repo.db_path) as conn:
                cur = conn.execute("SELECT id FROM materials")
                valid_mat_ids = {r[0] for r in cur.fetchall()}
        except Exception as e:
            print(f"[_heal_from_disk] 查询合法 materials 集合异常: {e}")

        # 1. 扫描 TASKS_DIR 自包含任务目录（成片画廊核心来源）
        if TASKS_DIR.exists():
            for task_dir in TASKS_DIR.iterdir():
                if not task_dir.is_dir():
                    continue
                manifest_path = task_dir / "project_manifest.json"
                if not manifest_path.exists():
                    continue
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        mdata = json.load(f)
                    pid = mdata.get("project_id") or mdata.get("id")
                    if not pid or pid in self._cache_by_proj_id:
                        continue

                    # 强校验：talking_head_id 必须存在于 materials 表，否则就地销毁残余目录禁止入库
                    th_id = mdata.get("talking_head_id")
                    if not th_id or th_id not in valid_mat_ids:
                        print(f"[_heal_from_disk] 发现孤儿任务目录（素材 {th_id} 不存在于 materials 表），就地销毁: {task_dir}")
                        shutil.rmtree(task_dir, ignore_errors=True)
                        continue

                    # 仅自愈真实压制完成的工程（视频文件 > 10KB，杜绝测试空文件入库）
                    vid_rel = mdata.get("output_video_path")
                    if not vid_rel:
                        continue
                    vid_p = resolve_media_path(vid_rel)
                    if not vid_p or not vid_p.exists() or vid_p.stat().st_size < 10 * 1024:
                        continue

                    subs = []
                    ass_p = task_dir / "subtitles.ass"
                    srt_p = task_dir / "subtitles.srt"
                    if ass_p.exists():
                        try:
                            subs = self._parse_ass_subtitles(ass_p.read_text(encoding="utf-8"))
                        except Exception:
                            subs = []
                    if not subs and srt_p.exists():
                        try:
                            subs = self._parse_srt(srt_p.read_text(encoding="utf-8"))
                        except Exception:
                            subs = []

                    proj = CutProject(
                        id=pid,
                        title=mdata.get("title") or task_dir.name,
                        talking_head_id=mdata.get("talking_head_id") or "",
                        aspect_ratio=mdata.get("aspect_ratio", "9:16"),
                        status=CutProjectStatus.COMPLETED,
                        output_video_path=mdata.get("output_video_path"),
                        task_dir=mdata.get("task_dir") or str(task_dir.relative_to(STORAGE_DIR.parent)).replace("\\", "/"),
                        cover_image_path=mdata.get("cover_image_path"),
                        cover_source=mdata.get("cover_source", "frame"),
                        subtitles=subs,
                        strategy=EditingStrategy(),
                        created_at=mdata.get("created_at", task_dir.stat().st_ctime),
                        updated_at=mdata.get("updated_at", task_dir.stat().st_mtime)
                    )
                    self.repo.save(proj)
                    self._cache_by_proj_id[proj.id] = proj
                    if proj.talking_head_id not in self._cache_by_th_id:
                        self._cache_by_th_id[proj.talking_head_id] = proj
                except Exception as e:
                    print(f"[ProjectStorageService] 从任务目录自愈工程失败 {task_dir}: {e}")

        # 2. 扫描 storage/projects/*.json (迁移入库后自动归档至 storage/legacy/projects/，实现 SQLite 单一权威)
        legacy_dir = STORAGE_DIR / "legacy" / "projects"
        if self.storage_dir and self.storage_dir.exists():
            for p_file in list(self.storage_dir.glob("*.json")):
                try:
                    with open(p_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    pid = data.get("id")
                    if pid and pid not in self._cache_by_proj_id:
                        p = CutProject(**data)
                        self.repo.save(p)
                        self._cache_by_proj_id[p.id] = p
                        if p.talking_head_id not in self._cache_by_th_id:
                            self._cache_by_th_id[p.talking_head_id] = p
                    # 归档移出 storage/projects/，避免重复自愈复活
                    legacy_dir.mkdir(parents=True, exist_ok=True)
                    dest_p = legacy_dir / p_file.name
                    if dest_p.exists():
                        dest_p.unlink()
                    shutil.move(str(p_file), str(dest_p))
                except Exception as e:
                    print(f"[ProjectStorageService] 迁移归档工程 JSON 失败 {p_file}: {e}")

    def _remove_shadow_json(self, project_id: Optional[str], talking_head_id: Optional[str]):
        """安全移除磁盘上遗留的影子 JSON 文件，杜绝自愈幽灵复活"""
        target_names = []
        if project_id:
            target_names.append(f"{project_id}.json")
        if talking_head_id:
            target_names.append(f"{talking_head_id}.json")

        dirs_to_check = [
            self.storage_dir,
            STORAGE_DIR / "legacy" / "projects"
        ]
        for d in dirs_to_check:
            if d and d.exists():
                for name in target_names:
                    f = d / name
                    if f.exists() and f.is_file():
                        try:
                            f.unlink()
                        except Exception as e:
                            print(f"[ProjectStorageService] 移除影子 JSON 失败 {f}: {e}")

    def prune_broken_drafts(self) -> int:
        """自动巡检并清理失效草稿（引用的口播素材在数据库中不存在或磁盘物理文件已丢失）"""
        from app.db.session import get_db_connection
        cleaned = 0
        try:
            with get_db_connection(self.repo.db_path) as conn:
                cur = conn.execute("SELECT id, talking_head_id, status, output_video_path FROM projects WHERE status = ?", (CutProjectStatus.DRAFT.value,))
                draft_rows = cur.fetchall()
                if not draft_rows:
                    return 0

                mat_cur = conn.execute("SELECT id, filepath FROM materials")
                mat_map = {row[0]: row[1] for row in mat_cur.fetchall()}

            for row in draft_rows:
                pid, th_id, status, out_v = row[0], row[1], row[2], row[3]
                if out_v:
                    continue

                is_broken = False
                if not th_id or th_id not in mat_map:
                    is_broken = True
                else:
                    rel_path = mat_map[th_id]
                    full_p = resolve_media_path(rel_path)
                    if not full_p or not full_p.exists():
                        is_broken = True

                if is_broken:
                    # 仅在口播素材已从 materials 表彻底删除时才物理清理；
                    # 若素材记录在库但物理文件暂不可达，绝不误删用户草稿
                    if not th_id or th_id not in mat_map:
                        print(f"[ProjectStorageService] 清理孤儿草稿工程: {pid} (th_id={th_id})")
                        self.delete_project(pid)
                        cleaned += 1
                    else:
                        print(f"[ProjectStorageService] 提示：草稿关联素材物理文件暂未就绪: {pid} (th_id={th_id})")
        except Exception as e:
            print(f"[ProjectStorageService] 巡检失效草稿失败: {e}")
        return cleaned

    def _load_all(self):
        """扫描 SQLite 权威库装载到内存索引，并执行自愈与健康清理"""
        self._cache_by_th_id.clear()
        self._cache_by_proj_id.clear()
        try:
            db_projects = self.repo.list_all()
            if db_projects:
                for p in db_projects:
                    if p.talking_head_id not in self._cache_by_th_id:
                        self._cache_by_th_id[p.talking_head_id] = p
                    self._cache_by_proj_id[p.id] = p
        except Exception:
            pass

        self._heal_from_disk()
        self.prune_broken_drafts()

    def get_by_material_id(self, talking_head_id: str) -> Optional[CutProject]:
        """根据口播素材 ID 获取专属工程缓存"""
        db_p = self.repo.get_by_material_id(talking_head_id)
        if db_p:
            self._cache_by_th_id[db_p.talking_head_id] = db_p
            self._cache_by_proj_id[db_p.id] = db_p
            return db_p
        return self._cache_by_th_id.get(talking_head_id)

    def get_by_project_id(self, project_id: str) -> Optional[CutProject]:
        """根据工程 ID 获取工程"""
        if project_id in self._cache_by_proj_id:
            return self._cache_by_proj_id[project_id]
        db_p = self.repo.get_by_id(project_id)
        if db_p:
            self._cache_by_th_id[db_p.talking_head_id] = db_p
            self._cache_by_proj_id[db_p.id] = db_p
            return db_p
        return None

    def save_project(self, project: CutProject) -> CutProject:
        if project.task_dir:
            project.task_dir = to_storage_relative(project.task_dir)
        if project.output_video_path:
            project.output_video_path = to_storage_relative(project.output_video_path)
        if project.cover_image_path:
            project.cover_image_path = to_storage_relative(project.cover_image_path)

        project.updated_at = time.time()
        self._cache_by_th_id[project.talking_head_id] = project
        self._cache_by_proj_id[project.id] = project

        try:
            self.repo.save(project)
        except Exception as e:
            raise RuntimeError(f"保存剪辑工程到 SQLite 失败: {e}") from e

        return project

    def cleanup_project_files(self, p: CutProject):
        """安全清理工程关联的磁盘生成文件及专属任务目录，彻底杜绝孤儿文件与幽灵复活"""
        # 1. 清理专属任务目录（包含 output_*.mp4, cover.jpg, subtitles.ass, project_manifest.json 等）
        if p.task_dir:
            try:
                td = resolve_media_path(p.task_dir) or (STORAGE_DIR.parent / p.task_dir).resolve()
                if td.exists() and td.is_dir() and (TASKS_DIR.resolve() in td.parents or "tasks" in td.parts):
                    shutil.rmtree(td, ignore_errors=True)
            except Exception as e:
                print(f"[ProjectStorageService] 清理任务目录失败 {p.task_dir}: {e}")

        # 2. 如果 output_video_path 位于历史 outputs 目录下，单独清理
        if p.output_video_path:
            try:
                vp = resolve_media_path(p.output_video_path) or (STORAGE_DIR.parent / p.output_video_path).resolve()
                if vp.exists() and vp.is_file() and (OUTPUTS_DIR.resolve() in vp.parents or TASKS_DIR.resolve() in vp.parents or "outputs" in vp.parts or "tasks" in vp.parts):
                    vp.unlink(missing_ok=True)
            except Exception as e:
                print(f"[ProjectStorageService] 清理成片视频文件失败 {p.output_video_path}: {e}")

        # 3. 如果 cover 位于历史 covers 目录下，单独清理
        if p.cover_image_path:
            try:
                cp = resolve_media_path(p.cover_image_path) or (STORAGE_DIR.parent / p.cover_image_path).resolve()
                if cp.exists() and cp.is_file() and (COVERS_DIR.resolve() in cp.parents or "covers" in cp.parts):
                    cp.unlink(missing_ok=True)
            except Exception as e:
                print(f"[ProjectStorageService] 清理封面文件失败 {p.cover_image_path}: {e}")

        # 4. 清理残留历史/影子 JSON，杜绝幽灵复活
        try:
            self._remove_shadow_json(p.id, p.talking_head_id)
        except Exception as e:
            print(f"[ProjectStorageService] 清理影子 JSON 失败: {e}")

    def delete_project_by_material(self, talking_head_id: str, only_draft: bool = True) -> bool:
        """按口播素材 ID 删除草稿工程与缓存（保护已完成成片成果）"""
        p = self.get_by_material_id(talking_head_id)
        if p and p.status == CutProjectStatus.COMPLETED and only_draft:
            return False

        # 删除数据库前显式调用 cleanup_project_files 彻底删除任务目录与清单文件
        if p:
            self.cleanup_project_files(p)

        proj_id = p.id if p else None
        db_deleted = False
        if not only_draft or (p and p.status != CutProjectStatus.COMPLETED):
            self._remove_shadow_json(proj_id, talking_head_id)

        try:
            db_deleted = self.repo.delete_by_material(talking_head_id, only_draft=only_draft)
            if proj_id and (not only_draft or (p and p.status != CutProjectStatus.COMPLETED)):
                self.repo.delete(proj_id)
        except Exception as e:
            print(f"[ProjectStorageService] 从 SQLite 删除工程失败: {e}")

        if not only_draft or (p and p.status != CutProjectStatus.COMPLETED):
            self._cache_by_th_id.pop(talking_head_id, None)
            if proj_id:
                self._cache_by_proj_id.pop(proj_id, None)

        return db_deleted or (p is not None)

    def delete_project(self, project_id: str, delete_files: bool = True) -> bool:
        """按工程 ID 精确删除指定工程、物理关联文件与缓存"""
        p = self.get_by_project_id(project_id)
        if p and delete_files:
            self.cleanup_project_files(p)

        self._cache_by_proj_id.pop(project_id, None)
        if p and p.talking_head_id and self._cache_by_th_id.get(p.talking_head_id) == p:
            self._cache_by_th_id.pop(p.talking_head_id, None)

        # 清理可能残留的影子/历史 JSON 文件，杜绝幽灵复活
        self._remove_shadow_json(project_id, p.talking_head_id if p else None)

        try:
            db_deleted = self.repo.delete(project_id)
            return db_deleted or (p is not None)
        except Exception as e:
            print(f"[ProjectStorageService] 从 SQLite 删除工程失败: {e}")
            return False

    def list_all_projects(self) -> List[CutProject]:
        """获取所有工程列表（权威 SQLite，按更新时间倒序）"""
        try:
            db_projects = self.repo.list_all()
            if db_projects:
                for p in db_projects:
                    self._cache_by_proj_id[p.id] = p
                    if p.talking_head_id not in self._cache_by_th_id:
                        self._cache_by_th_id[p.talking_head_id] = p
                return db_projects
        except Exception:
            pass

        # 若 SQLite 为空，尝试自愈并重新拉取
        self._heal_from_disk()
        try:
            db_projects = self.repo.list_all()
            if db_projects:
                for p in db_projects:
                    self._cache_by_proj_id[p.id] = p
                    if p.talking_head_id not in self._cache_by_th_id:
                        self._cache_by_th_id[p.talking_head_id] = p
                return db_projects
        except Exception:
            pass

        return list(self._cache_by_proj_id.values())

project_storage_service = ProjectStorageService()
