import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from app.core.config import PROJECTS_DIR
from app.models.entities import CutProject

class ProjectStorageService:
    def __init__(self, storage_dir: Path = PROJECTS_DIR):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache_by_th_id: Dict[str, CutProject] = {}
        self._cache_by_proj_id: Dict[str, CutProject] = {}
        self._load_all()

    def _load_all(self):
        """扫描磁盘上的所有工程 JSON 文件并装载到内存索引"""
        self._cache_by_th_id.clear()
        self._cache_by_proj_id.clear()
        
        if not self.storage_dir.exists():
            return

        for json_file in self.storage_dir.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    project = CutProject(**data)
                    self._cache_by_th_id[project.talking_head_id] = project
                    self._cache_by_proj_id[project.id] = project
            except Exception as e:
                print(f"[ProjectStorageService] 载入工程缓存文件失败 {json_file}: {e}")

    def get_by_material_id(self, talking_head_id: str) -> Optional[CutProject]:
        """根据口播视频素材 ID 获取专属工程缓存"""
        if talking_head_id in self._cache_by_th_id:
            return self._cache_by_th_id[talking_head_id]
        
        # 尝试二次从磁盘装载
        target_file = self.storage_dir / f"{talking_head_id}.json"
        if target_file.exists():
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    p = CutProject(**data)
                    self._cache_by_th_id[p.talking_head_id] = p
                    self._cache_by_proj_id[p.id] = p
                    return p
            except Exception as e:
                print(f"[ProjectStorageService] 从磁盘读取工程失败: {e}")
        return None

    def get_by_project_id(self, project_id: str) -> Optional[CutProject]:
        """根据工程 ID 获取工程"""
        if project_id in self._cache_by_proj_id:
            return self._cache_by_proj_id[project_id]
        # 若内存未命中，重载磁盘后再试
        self._load_all()
        return self._cache_by_proj_id.get(project_id)

    def save_project(self, project: CutProject) -> CutProject:
        """保存工程至内存并原子写入磁盘 storage/projects/{talking_head_id}.json"""
        project.updated_at = time.time()
        self._cache_by_th_id[project.talking_head_id] = project
        self._cache_by_proj_id[project.id] = project

        target_file = self.storage_dir / f"{project.talking_head_id}.json"
        temp_file = self.storage_dir / f"{project.talking_head_id}.tmp"

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(project.model_dump(), f, ensure_ascii=False, indent=2)
            temp_file.replace(target_file)
        except Exception as e:
            print(f"[ProjectStorageService] 写入工程持久化文件失败: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            # 尝试直接写入目标文件
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(project.model_dump(), f, ensure_ascii=False, indent=2)

        return project

    def delete_project_by_material(self, talking_head_id: str) -> bool:
        """按口播素材 ID 删除工程文件与缓存"""
        p = self._cache_by_th_id.pop(talking_head_id, None)
        if p and p.id in self._cache_by_proj_id:
            self._cache_by_proj_id.pop(p.id, None)

        target_file = self.storage_dir / f"{talking_head_id}.json"
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
        """获取所有工程列表"""
        return list(self._cache_by_proj_id.values())

project_storage_service = ProjectStorageService()
