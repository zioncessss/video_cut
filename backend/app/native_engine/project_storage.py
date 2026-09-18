import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import PROJECTS_DIR, ensure_storage_path
from app.models.entities import CutProject
from app.db.repository import ProjectRepository

# 工程 ID 必须为安全标识符（UUID/素材 ID），杜绝路径穿越
_SAFE_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

def _safe_project_file(storage_dir: Path, talking_head_id: str, suffix: str = ".json") -> Path:
    if not _SAFE_PROJECT_ID_RE.fullmatch(talking_head_id):
        raise ValueError(f"非法工程素材 ID: {talking_head_id!r}")
    return ensure_storage_path(storage_dir / f"{talking_head_id}{suffix}")

class ProjectStorageService:
    def __init__(self, storage_dir: Path = PROJECTS_DIR, db_path=None):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.repo = ProjectRepository(db_path)
        self._cache_by_th_id: Dict[str, CutProject] = {}
        self._cache_by_proj_id: Dict[str, CutProject] = {}
        self._load_all()

    def _load_all(self):
        """扫描 SQLite 数据库与磁盘 JSON 文件并装载到内存索引"""
        self._cache_by_th_id.clear()
        self._cache_by_proj_id.clear()
        
        # 1. 优先从 SQLite 读
        try:
            db_projects = self.repo.list_all()
            if db_projects:
                for p in db_projects:
                    # db_projects 已按 updated_at DESC 排序，仅将最新的工程映射给 talking_head_id，杜绝旧版本覆盖新版本
                    if p.talking_head_id not in self._cache_by_th_id:
                        self._cache_by_th_id[p.talking_head_id] = p
                    self._cache_by_proj_id[p.id] = p
                return
        except Exception:
            pass

        # 2. 回退扫描磁盘 JSON 文件并写入 SQLite
        if not self.storage_dir.exists():
            return

        for json_file in self.storage_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    project = CutProject(**data)
                    self._cache_by_th_id[project.talking_head_id] = project
                    self._cache_by_proj_id[project.id] = project
                    try:
                        self.repo.save(project)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[ProjectStorageService] 载入工程缓存文件失败 {json_file}: {e}")

    def get_by_material_id(self, talking_head_id: str) -> Optional[CutProject]:
        """根据口播视频素材 ID 获取专属工程缓存"""
        db_p = self.repo.get_by_material_id(talking_head_id)
        if db_p:
            self._cache_by_th_id[db_p.talking_head_id] = db_p
            self._cache_by_proj_id[db_p.id] = db_p
            return db_p

        if talking_head_id in self._cache_by_th_id:
            return self._cache_by_th_id[talking_head_id]

        # 尝试二次从磁盘装载
        target_file = _safe_project_file(self.storage_dir, talking_head_id)
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    p = CutProject(**data)
                    self._cache_by_th_id[p.talking_head_id] = p
                    self._cache_by_proj_id[p.id] = p
                    try:
                        self.repo.save(p)
                    except Exception:
                        pass
                    return p
            except Exception as e:
                print(f"[ProjectStorageService] 从磁盘读取工程失败: {e}")
        return None

    def get_by_project_id(self, project_id: str) -> Optional[CutProject]:
        """根据工程 ID 获取工程"""
        if project_id in self._cache_by_proj_id:
            return self._cache_by_proj_id[project_id]
        db_p = self.repo.get_by_id(project_id)
        if db_p:
            self._cache_by_th_id[db_p.talking_head_id] = db_p
            self._cache_by_proj_id[db_p.id] = db_p
            return db_p
        # 若内存未命中，重载磁盘后再试
        self._load_all()
        return self._cache_by_proj_id.get(project_id)

    def save_project(self, project: CutProject) -> CutProject:
        """保存工程至 SQLite（唯一权威存储）。

        SQLite 写失败时抛出真实异常（真实执行铁律：不允许静默假装成功）。
        磁盘 JSON 影子文件仅在 VIDEOCUT_LEGACY_JSON=1 时同步写一份（迁移期调试开关，默认关闭）。
        """
        project.updated_at = time.time()
        # 确保该口播素材在缓存与 SQLite 中只有唯一权威工程，清理可能残留的历史旧版本
        old_p = self._cache_by_th_id.get(project.talking_head_id)
        if old_p and old_p.id != project.id:
            try:
                self.repo.delete(old_p.id)
                self._cache_by_proj_id.pop(old_p.id, None)
            except Exception:
                pass

        self._cache_by_th_id[project.talking_head_id] = project
        self._cache_by_proj_id[project.id] = project

        try:
            self.repo.save(project)
        except Exception as e:
            raise RuntimeError(f"保存剪辑工程到 SQLite 失败: {e}") from e

        if os.getenv("VIDEOCUT_LEGACY_JSON", "") == "1":
            target_file = _safe_project_file(self.storage_dir, project.talking_head_id)
            temp_file = _safe_project_file(self.storage_dir, project.talking_head_id, ".tmp")
            try:
                temp_file.write_text(
                    json.dumps(project.model_dump(), ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                temp_file.replace(target_file)
            except Exception as e:
                print(f"[ProjectStorageService] 影子 JSON 写入失败（不影响权威存储）: {e}")

        return project

    def delete_project_by_material(self, talking_head_id: str) -> bool:
        """按口播素材 ID 删除工程文件与缓存"""
        try:
            self.repo.delete_by_material(talking_head_id)
        except Exception as e:
            print(f"[ProjectStorageService] 从 SQLite 删除工程失败: {e}")

        p = self._cache_by_th_id.pop(talking_head_id, None)
        if p and p.id in self._cache_by_proj_id:
            self._cache_by_proj_id.pop(p.id, None)

        target_file = _safe_project_file(self.storage_dir, talking_head_id)
        if target_file.exists():
            try:
                target_file.unlink()
                return True
            except Exception as e:
                print(f"[ProjectStorageService] 删除磁盘工程文件失败: {e}")
        return p is not None

    def delete_project(self, project_id: str) -> bool:
        """按工程 ID 删除工程文件与缓存"""
        p = self._cache_by_proj_id.get(project_id)
        if p:
            return self.delete_project_by_material(p.talking_head_id)
        return False

    def list_all_projects(self) -> List[CutProject]:
        """获取所有工程列表（优先权威 SQLite，按更新时间倒序）"""
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
