import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Dict
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
        try:
            META_FILE.write_text(
                json.dumps([m.model_dump() for m in self._cache.values()], ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"Error saving materials meta: {e}")

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

    def save_material(self, category: MaterialCategory, filename: str, source_path_or_bytes) -> Material:
        target_dir = CATEGORY_DIRS[category.value]
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            ext = ".mp4"

        # 文件名净化：仅保留安全字符并截断长度，杜绝路径穿越
        raw_stem = _SAFE_FILENAME_RE.sub("_", Path(filename).stem)[:80].strip("._") or "material"
        dest_path = ensure_storage_path(target_dir / f"{raw_stem}_{int(time.time() * 1000)}{ext}")

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
                    "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    str(conv_tmp)
                ]
                if subprocess.run(conv_cmd, capture_output=True, timeout=120).returncode == 0:
                    dest_path.unlink()
                    conv_tmp.rename(dest_path)
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
            fps=metadata["fps"]
        )
        self._cache[material.id] = material
        # 真实执行铁律：入库失败必须如实报错（如旧库 CHECK 未迁移），严禁文件已落盘却假装成功
        try:
            self.repo.save(material)
        except Exception as e:
            self._cache.pop(material.id, None)
            raise RuntimeError(
                f"素材写入权威库失败（若为旧版分类约束导致，请重启应用自动完成 005 分类迁移）: {e}"
            ) from e
        self._save_meta()
        return material

    def get_material(self, material_id: str) -> Optional[Material]:
        db_mat = self.repo.get_by_id(material_id)
        if db_mat:
            self._cache[db_mat.id] = db_mat
            return db_mat
        return self._cache.get(material_id)

    def list_materials(self, category: Optional[MaterialCategory] = None) -> List[Material]:
        try:
            db_list = self.repo.list_all(category)
            if db_list:
                for m in db_list:
                    self._cache[m.id] = m
                return db_list
        except Exception:
            pass

        if category:
            return [m for m in self._cache.values() if m.category == category]
        return list(self._cache.values())

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

        return deleted or (m is not None)

storage_service = StorageService()
