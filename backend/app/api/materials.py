from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List, Optional
from pathlib import Path
from app.models.entities import Material, MaterialCategory
from app.native_engine.storage import storage_service

router = APIRouter()

from pydantic import BaseModel

class LocalImportRequest(BaseModel):
    category: MaterialCategory
    file_path: str

@router.post("/upload", response_model=Material)
async def upload_material(
    category: MaterialCategory = Form(...),
    file: UploadFile = File(...)
):
    try:
        content = await file.read()
        material = storage_service.save_material(
            category=category,
            filename=file.filename or "video.mp4",
            source_path_or_bytes=content
        )
        return material
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload material: {str(e)}")

@router.post("/import-local", response_model=Material)
async def import_local_material(payload: LocalImportRequest):
    """Electron 原生桌面端零拷贝极速导入本地视频文件"""
    p = Path(payload.file_path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=400, detail="指定的本地文件不存在")
    try:
        material = storage_service.save_material(
            category=payload.category,
            filename=p.name,
            source_path_or_bytes=p
        )
        return material
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入本地素材失败: {str(e)}")

@router.get("", response_model=List[Material])
async def list_materials(category: Optional[MaterialCategory] = None):
    return storage_service.list_materials(category=category)

@router.get("/{material_id}", response_model=Material)
async def get_material(material_id: str):
    m = storage_service.get_material(material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return m

@router.delete("/{material_id}")
async def delete_material(material_id: str):
    success = storage_service.delete_material(material_id)
    if not success:
        raise HTTPException(status_code=404, detail="Material not found")
    return {"code": 0, "message": "Material deleted successfully"}
