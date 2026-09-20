import time
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import PROJECTS_DIR
from app.models.entities import CutProject
from app.db.repository import ProjectRepository

class ProjectStorageService:
    def __init__(self, storage_dir: Path = PROJECTS_DIR, db_path=None):
        self.storage_dir = storage_dir
        self.repo = ProjectRepository(db_path)
        self._cache_by_th_id: Dict[str, CutProject] = {}
        self._cache_by_proj_id: Dict[str, CutProject] = {}
        self._load_all()

    def _load_all(self):
        """扫描 SQLite 权威库装载到内存索引"""
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
        """保存工程至 SQLite（唯一权威存储）"""
        project.updated_at = time.time()
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

        return project

    def delete_project_by_material(self, talking_head_id: str) -> bool:
        """按口播素材 ID 删除工程与缓存"""
        p = self.get_by_material_id(talking_head_id)
        proj_id = p.id if p else None

        db_deleted = False
        try:
            db_deleted = self.repo.delete_by_material(talking_head_id)
            if proj_id:
                self.repo.delete(proj_id)
        except Exception as e:
            print(f"[ProjectStorageService] 从 SQLite 删除工程失败: {e}")

        self._cache_by_th_id.pop(talking_head_id, None)
        if proj_id:
            self._cache_by_proj_id.pop(proj_id, None)

        return db_deleted or (p is not None)

    def delete_project(self, project_id: str) -> bool:
        """按工程 ID 删除工程与缓存"""
        p = self.get_by_project_id(project_id)
        if p and p.talking_head_id:
            return self.delete_project_by_material(p.talking_head_id)
        self._cache_by_proj_id.pop(project_id, None)
        try:
            return self.repo.delete(project_id)
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
        return list(self._cache_by_proj_id.values())

project_storage_service = ProjectStorageService()
