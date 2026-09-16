import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
from app.core.config import CATEGORY_DIRS, STORAGE_DIR, ALLOWED_VIDEO_EXTENSIONS
from app.models.entities import Material, MaterialCategory

META_FILE = STORAGE_DIR / "materials_meta.json"

class StorageService:
    def __init__(self):
        self.meta_file = META_FILE
        self._cache: Dict[str, Material] = {}
        self._load_meta()

    def _load_meta(self):
        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        m = Material(**item)
                        self._cache[m.id] = m
            except Exception:
                self._cache = {}

    def _save_meta(self):
        try:
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump([m.model_dump() for m in self._cache.values()], f, ensure_ascii=False, indent=2)
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
            
        safe_name = f"{Path(filename).stem}_{int(os.times().elapsed * 1000)}{ext}"
        dest_path = target_dir / safe_name

        if isinstance(source_path_or_bytes, (str, Path)):
            shutil.copyfile(str(source_path_or_bytes), str(dest_path))
        else:
            with open(dest_path, "wb") as f:
                f.write(source_path_or_bytes)

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
        self._save_meta()
        return material

    def get_material(self, material_id: str) -> Optional[Material]:
        return self._cache.get(material_id)

    def list_materials(self, category: Optional[MaterialCategory] = None) -> List[Material]:
        if category:
            return [m for m in self._cache.values() if m.category == category]
        return list(self._cache.values())

    def delete_material(self, material_id: str) -> bool:
        m = self._cache.pop(material_id, None)
        if m:
            self._save_meta()
            full_path = STORAGE_DIR.parent / m.filepath
            if full_path.exists():
                try:
                    full_path.unlink()
                except Exception:
                    pass
            return True
        return False

storage_service = StorageService()
