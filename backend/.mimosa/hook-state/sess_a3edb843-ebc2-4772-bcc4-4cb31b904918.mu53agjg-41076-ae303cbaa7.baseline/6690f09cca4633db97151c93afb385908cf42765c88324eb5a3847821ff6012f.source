import json
from pathlib import Path
from typing import Optional
from app.core.config import STORAGE_DIR, PROJECTS_DIR, SETTINGS_FILE
from app.db.session import init_db
from app.db.repository import MaterialRepository, ProjectRepository, SettingsRepository
from app.models.entities import Material, CutProject

META_FILE = STORAGE_DIR / "materials_meta.json"

def migrate_legacy_data(db_path: Optional[Path] = None):
    """平滑升级：将旧版 materials_meta.json、projects/*.json 与 settings.json 迁移至 SQLite"""
    init_db(db_path)
    
    mat_repo = MaterialRepository(db_path)
    proj_repo = ProjectRepository(db_path)
    settings_repo = SettingsRepository(db_path)

    # 0. 检查是否已完成过历史数据迁移，避免重复执行与已删除素材死灰复燃
    if settings_repo.get("legacy_data_migrated") == "1":
        return

    # 1. 迁移素材元数据
    if META_FILE.exists():
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                materials_data = json.load(f)
                for item in materials_data:
                    m = Material(**item)
                    if not mat_repo.get_by_id(m.id):
                        mat_repo.save(m)
        except Exception as e:
            print(f"[Migrator] 迁移 materials_meta.json 异常: {e}")

    # 2. 迁移持久化剪辑工程
    if PROJECTS_DIR.exists():
        for p_file in PROJECTS_DIR.glob("*.json"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    proj_data = json.load(f)
                    p = CutProject(**proj_data)
                    # 严禁捏造虚假占位素材！若口播素材已被物理清理，此工程为孤儿残留，直接清理该文件并跳过
                    if not mat_repo.get_by_id(p.talking_head_id):
                        try:
                            p_file.unlink()
                        except Exception:
                            pass
                        continue

                    if not proj_repo.get_by_id(p.id):
                        proj_repo.save(p)
            except Exception as e:
                print(f"[Migrator] 迁移工程文件 {p_file} 异常: {e}")

    # 3. 迁移配置数据
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
                for k, v in settings_data.items():
                    if settings_repo.get(k) is None:
                        settings_repo.set(k, str(v))
        except Exception as e:
            print(f"[Migrator] 迁移 settings.json 异常: {e}")

    try:
        settings_repo.set("legacy_data_migrated", "1")
    except Exception as e:
        print(f"[Migrator] 记录迁移标记异常: {e}")
