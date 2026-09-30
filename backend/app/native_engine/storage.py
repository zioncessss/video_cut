import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
from app.core.config import CATEGORY_DIRS, STORAGE_DIR, ALLOWED_VIDEO_EXTENSIONS, ensure_storage_path
from app.models.entities import Material, MaterialCategory
from app.db.repository import MaterialRepository

META_FILE = STORAGE_DIR / "materials_meta.json"

# 上传文件名仅保留安全字符，杜绝路径穿越与非法字符落盘
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9\u4e00-\u9fff._-]")

class StorageService:
    def __init__(self, db_path=None):
        self.meta_file = META_FILE
        self.repo = MaterialRepository(db_path)
        self._cache: Dict[str, Material] = {}
        self._load_meta()

    def _load_meta(self):
        try:
            db_materials = self.repo.list_all()
            if db_materials:
                for m in db_materials:
                    self._cache[m.id] = m
                return
        except Exception:
            pass

        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        m = Material(**item)
                        self._cache[m.id] = m
                        try:
                            self.repo.save(m)
                        except Exception:
                            pass
            except Exception:
                self._cache = {}

    def _save_meta(self):
        """已废弃的 JSON 影子写路径：SQLite 是素材元数据唯一权威存储。

        保留空实现以兼容历史调用点；materials_meta.json 仅作为一次性迁移输入由 migrator 读取。
        """
        return

    def probe_video_metadata(self, filepath: Path) -> Dict[str, any]:
        """使用 ffprobe 探测视频时长、长宽、帧率"""
        meta = {"duration": 0.0, "width": 1080, "height": 1920, "fps": 30.0}
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
                "-of", "json",
                str(filepath)
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                format_info = data.get("format", {})
                if streams:
                    s = streams[0]
                    meta["width"] = int(s.get("width", 1080))
                    meta["height"] = int(s.get("height", 1920))
                    fps_str = s.get("r_frame_rate", "30/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        if float(den) > 0:
                            meta["fps"] = round(float(num) / float(den), 2)
                    duration_s = s.get("duration") or format_info.get("duration")
                    if duration_s:
                        meta["duration"] = round(float(duration_s), 3)
        except Exception:
            # ffprobe 未安装或执行超时时的安全默认兜底
            pass
        return meta

    @staticmethod
    def compute_file_hash(source_path_or_bytes) -> Tuple[str, int]:
        """计算视频内容的 SHA-256 哈希值与文件字节大小，用于精准查重与幂等写盘"""
        hasher = hashlib.sha256()
        total_size = 0
        if isinstance(source_path_or_bytes, (str, Path)):
            with open(source_path_or_bytes, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    hasher.update(chunk)
                    total_size += len(chunk)
        else:
            total_size = len(source_path_or_bytes)
            hasher.update(source_path_or_bytes)
        return hasher.hexdigest(), total_size

    def save_material(self, category: MaterialCategory, filename: str, source_path_or_bytes, plate_region: Optional[str] = None) -> Material:
        target_dir = CATEGORY_DIRS[category.value]
        target_dir.mkdir(parents=True, exist_ok=True)

        content_hash, file_size = self.compute_file_hash(source_path_or_bytes)

        # 1. 精准查重 (Deduplication)：优先检查数据库中是否已存在内容完全一致且物理文件存在的素材
        existing_matches = self.repo.find_by_hash(content_hash)
        for cand in existing_matches:
            full_cand_path = (STORAGE_DIR.parent / cand.filepath).resolve()
            if full_cand_path.exists() and full_cand_path.stat().st_size > 0:
                if cand.category == category:
                    # 同分类完全一致：若传入了新的 plate_region 则更新属性
                    if plate_region and cand.plate_region != plate_region:
                        cand.plate_region = plate_region
                        self.repo.update_plate_region(cand.id, plate_region)
                    self._cache[cand.id] = cand
                    return cand
                else:
                    # 跨分类复用同一底层物理文件
                    material = Material(
                        category=category,
                        filename=filename,
                        filepath=cand.filepath,
                        duration=cand.duration,
                        width=cand.width,
                        height=cand.height,
                        fps=cand.fps,
                        content_hash=content_hash,
                        file_size=file_size,
                        plate_region=plate_region
                    )
                    self._cache[material.id] = material
                    self.repo.save(material)
                    return material

        # 存量未登记 content_hash 的素材做物理大小及哈希兜底查重
        all_materials = self.repo.list_all(category)
        for cand in all_materials:
            if cand.content_hash:
                continue
            full_cand_path = (STORAGE_DIR.parent / cand.filepath).resolve()
            if full_cand_path.exists() and full_cand_path.stat().st_size == file_size:
                cand_hash, _ = self.compute_file_hash(full_cand_path)
                cand.content_hash = cand_hash
                cand.file_size = file_size
                if plate_region and cand.plate_region != plate_region:
                    cand.plate_region = plate_region
                    self.repo.update_plate_region(cand.id, plate_region)
                self.repo.save(cand)
                if cand_hash == content_hash:
                    self._cache[cand.id] = cand
                    return cand

        # 2. 幂等写盘：使用确定性文件名（前缀+哈希指纹），杜绝时间戳导致的多份冗余文件
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError(f"不支持的视频格式: '{ext}'，仅支持 {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")
        raw_stem = _SAFE_FILENAME_RE.sub("_", Path(filename).stem)[:60].strip("._") or "material"
        deterministic_name = f"{raw_stem}_{content_hash[:12]}{ext}"
        dest_path = ensure_storage_path(target_dir / deterministic_name)

        if not dest_path.exists() or dest_path.stat().st_size != file_size:
            if isinstance(source_path_or_bytes, (str, Path)):
                shutil.copyfile(str(source_path_or_bytes), str(dest_path))
            else:
                dest_path.write_bytes(source_path_or_bytes)

            # 视频编码兼容性保护：检测是否为 HEVC/H.265 或非标准编码，自动转为浏览器万能支持的 H.264
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1",
                    str(dest_path)
                ]
                c_res = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                if c_res.returncode == 0 and c_res.stdout.strip() and c_res.stdout.strip() != "h264":
                    conv_tmp = dest_path.with_name(f"{dest_path.stem}_conv.mp4")
                    conv_cmd = [
                        "ffmpeg", "-y", "-i", str(dest_path),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "aac", "-b:a", "320k", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        str(conv_tmp)
                    ]
                    if subprocess.run(conv_cmd, capture_output=True, timeout=120).returncode == 0:
                        dest_path.unlink()
                        conv_tmp.rename(dest_path)
                        content_hash, file_size = self.compute_file_hash(dest_path)
            except Exception:
                pass

        metadata = self.probe_video_metadata(dest_path)
        rel_path = str(dest_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/")

        material = Material(
            category=category,
            filename=filename,
            filepath=rel_path,
            duration=metadata["duration"],
            width=metadata["width"],
            height=metadata["height"],
            fps=metadata["fps"],
            content_hash=content_hash,
            file_size=file_size,
            plate_region=plate_region
        )
        self._cache[material.id] = material
        # 真实执行铁律：入库失败必须如实报错
        try:
            self.repo.save(material)
        except Exception as e:
            self._cache.pop(material.id, None)
            raise RuntimeError(f"素材写入权威库失败: {e}") from e
        self._save_meta()
        return material

    def update_material_region(self, material_id: str, plate_region: Optional[str]) -> bool:
        ok = self.repo.update_plate_region(material_id, plate_region)
        if ok and material_id in self._cache:
            self._cache[material_id].plate_region = plate_region
        return ok

    def get_material(self, material_id: str) -> Optional[Material]:
        db_mat = self.repo.get_by_id(material_id)
        if db_mat:
            self._cache[db_mat.id] = db_mat
            return db_mat
        return self._cache.get(material_id)

    def list_materials(self, category: Optional[MaterialCategory] = None, plate_region: Optional[str] = None) -> List[Material]:
        try:
            db_list = self.repo.list_all(category, plate_region)
            if db_list is not None:
                for m in db_list:
                    self._cache[m.id] = m
                return db_list
        except Exception:
            pass

        items = list(self._cache.values())
        if category:
            items = [m for m in items if m.category == category]
        if plate_region:
            items = [m for m in items if m.plate_region == plate_region]
        return items

    def delete_material(self, material_id: str) -> bool:
        m = self.get_material(material_id)
        deleted = self.repo.delete(material_id)
        self._cache.pop(material_id, None)
        self._save_meta()

        if m:
            # 物理文件仅在无其他素材记录引用同一文件时才删除（防御历史重复登记导致另一分类"消失"）
            still_referenced = any(
                x.filepath == m.filepath
                for x in list(self._cache.values())
                if x.id != material_id
            ) or any(
                x.filepath == m.filepath and x.id != material_id
                for x in self.repo.list_all()
            )
            if not still_referenced:
                full_path = STORAGE_DIR.parent / m.filepath
                if full_path.exists():
                    try:
                        full_path.unlink()
                    except Exception:
                        pass

        # 级联清理关联剪辑工程持久化文件与内存缓存
        try:
            from app.native_engine.project_storage import project_storage_service
            project_storage_service.delete_project_by_material(material_id)
        except Exception as e:
            print(f"[StorageService] 级联删除工程异常: {e}")

        # 级联保护：若被删素材为空镜素材，联动将存量工程的 subtitles.broll_material_id 与对应 broll_replacements 进行解绑置空保护
        try:
            from app.native_engine.project_storage import project_storage_service
            all_projects = project_storage_service.list_all_projects()
            for p in all_projects:
                p_modified = False
                for s in p.subtitles:
                    if s.broll_material_id == material_id:
                        s.broll_material_id = None
                        p_modified = True
                    if s.scene_decision and s.scene_decision.material_id == material_id:
                        s.scene_decision.material_id = None
                        p_modified = True
                for s in (p.compact_subtitles or []):
                    if s.broll_material_id == material_id:
                        s.broll_material_id = None
                        p_modified = True
                    if s.scene_decision and s.scene_decision.material_id == material_id:
                        s.scene_decision.material_id = None
                        p_modified = True
                if p.broll_replacements:
                    orig_len = len(p.broll_replacements)
                    p.broll_replacements = [r for r in p.broll_replacements if r.material_id != material_id]
                    if len(p.broll_replacements) != orig_len:
                        p_modified = True
                if p_modified:
                    project_storage_service.save_project(p)
        except Exception as e:
            print(f"[StorageService] 解绑空镜素材引用异常: {e}")

        return deleted or (m is not None)

    def cleanup_materials(self, dry_run: bool = False) -> Dict[str, Any]:
        """全面清理素材库：
        1. 清除已知测试垃圾文件（如 batch_bad_*.mp4, batch_ok_*.mp4 等）与未登记的孤儿文件；
        2. 重复素材按 content_hash 自动去重合并：保留被工程引用的记录，将重复引用无损重定向到权威素材，并释放冗余磁盘空间。
        """
        from app.db.session import get_db_connection
        freed_bytes = 0
        removed_files: List[str] = []
        merged_materials: List[Dict[str, Any]] = []

        # 1. 扫描并收集数据库内合法素材与工程引用
        with get_db_connection(self.repo.db_path) as conn:
            cur = conn.execute("SELECT id, category, filename, filepath, content_hash, file_size FROM materials")
            db_materials = cur.fetchall()

            # 查出当前被所有工程引用的 talking_head_id 集合
            p_cur = conn.execute("SELECT id, talking_head_id, brolls_json FROM projects")
            project_rows = p_cur.fetchall()

        used_mat_ids = set()
        for prow in project_rows:
            if prow[1]:
                used_mat_ids.add(prow[1])
            if prow[2]:
                try:
                    b_list = json.loads(prow[2])
                    for b in b_list:
                        if isinstance(b, dict) and b.get("material_id"):
                            used_mat_ids.add(b["material_id"])
                except Exception:
                    pass

        # 建立合法物理路径相对路径集合（统一斜杠）
        valid_rel_paths = set()
        for row in db_materials:
            p_str = (row[3] or "").replace("\\", "/").strip("/")
            if p_str:
                valid_rel_paths.add(p_str)

        # 2. 清理磁盘孤儿与测试垃圾文件
        for cat_dir in CATEGORY_DIRS.values():
            if not cat_dir.exists():
                continue
            for file_path in cat_dir.glob("*.mp4"):
                rel_str = str(file_path.relative_to(STORAGE_DIR.parent)).replace("\\", "/").strip("/")
                fname = file_path.name
                fsize = file_path.stat().st_size

                # 识别测试垃圾文件：如 batch_bad_*, batch_ok_* 等
                is_test_junk = (fname.startswith("batch_bad_") or fname.startswith("batch_ok_") or fname.startswith("test_fake_")) and fsize < 1024 * 1024
                # 识别孤儿文件：既非测试垃圾，又未被 materials 表登记
                is_orphan = (rel_str not in valid_rel_paths)

                if is_test_junk or is_orphan:
                    freed_bytes += fsize
                    removed_files.append(rel_str)
                    if not dry_run:
                        try:
                            file_path.unlink(missing_ok=True)
                        except Exception as e:
                            print(f"[cleanup] 删除孤儿/测试文件失败 {rel_str}: {e}")

        # 3. 补全存量素材的 content_hash 与 file_size 并按内容查重合并
        mat_models = self.repo.list_all()
        hash_to_materials: Dict[str, List[Material]] = {}
        for m in mat_models:
            full_p = (STORAGE_DIR.parent / m.filepath).resolve()
            if not full_p.exists():
                # 物理文件已不存在，清理此失效记录
                if not dry_run:
                    self.repo.delete(m.id)
                    self._cache.pop(m.id, None)
                continue

            c_hash = m.content_hash
            c_size = m.file_size or full_p.stat().st_size
            if not c_hash:
                c_hash, c_size = self.compute_file_hash(full_p)
                m.content_hash = c_hash
                m.file_size = c_size
                if not dry_run:
                    self.repo.save(m)

            key = f"{m.category.value}_{c_hash}"
            hash_to_materials.setdefault(key, []).append(m)

        # 对同一分类下 hash 相同的重复记录执行合并
        for key, group in hash_to_materials.items():
            if len(group) <= 1:
                continue

            # 选出权威记录：优先选被工程引用的记录（且按最早创建优先）；若均无工程引用则选最早创建的一条
            used_in_group = [x for x in group if x.id in used_mat_ids]
            if used_in_group:
                chosen = sorted(used_in_group, key=lambda x: x.created_at)[0]
            else:
                chosen = sorted(group, key=lambda x: x.created_at)[0]

            duplicates = [x for x in group if x.id != chosen.id]
            merged_info = {
                "chosen_id": chosen.id,
                "chosen_file": chosen.filepath,
                "duplicate_ids": [d.id for d in duplicates],
                "duplicate_files": [d.filepath for d in duplicates],
            }
            merged_materials.append(merged_info)

            if not dry_run:
                with get_db_connection(self.repo.db_path) as conn:
                    for dup in duplicates:
                        # 若有工程引用了 dup.id，将其无损重定向到 chosen.id
                        conn.execute("UPDATE projects SET talking_head_id = ? WHERE talking_head_id = ?", (chosen.id, dup.id))
                        # 从 materials 表中删除重复记录
                        conn.execute("DELETE FROM materials WHERE id = ?", (dup.id,))
                        self._cache.pop(dup.id, None)

                        # 如果 dup 的物理文件与 chosen 的物理文件不同，删除冗余物理文件
                        if dup.filepath != chosen.filepath:
                            dup_path = (STORAGE_DIR.parent / dup.filepath).resolve()
                            if dup_path.exists() and dup_path != (STORAGE_DIR.parent / chosen.filepath).resolve():
                                freed_bytes += dup_path.stat().st_size
                                try:
                                    dup_path.unlink(missing_ok=True)
                                except Exception as e:
                                    print(f"[cleanup] 删除重复物理文件失败 {dup.filepath}: {e}")

        return {
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "removed_files_count": len(removed_files),
            "removed_files": removed_files,
            "merged_materials_count": len(merged_materials),
            "merged_materials": merged_materials
        }

storage_service = StorageService()
