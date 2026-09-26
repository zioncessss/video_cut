from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel
from app.models.entities import Material, MaterialCategory
from app.native_engine.storage import storage_service
from app.core.plate_regions import ZHEJIANG_REGIONS, is_valid_zhejiang_region, normalize_region_code

router = APIRouter()

class LocalImportRequest(BaseModel):
    category: MaterialCategory
    file_path: str
    plate_region: Optional[str] = None

class UpdateMaterialRegionRequest(BaseModel):
    plate_region: Optional[str] = None

@router.get("/regions/zhejiang")
async def list_zhejiang_regions() -> List[Dict[str, Any]]:
    """获取浙江 11 地市标准车牌常识字典"""
    return [
        {
            "code": r.code,
            "plate_prefix": r.plate_prefix,
            "city_name": r.city_name,
            "districts": r.districts,
            "landmarks": r.landmarks
        }
        for r in ZHEJIANG_REGIONS
    ]

@router.post("/upload", response_model=Material)
async def upload_material(
    category: MaterialCategory = Form(...),
    file: UploadFile = File(...),
    plate_region: Optional[str] = Form(None)
):
    try:
        norm_region = normalize_region_code(plate_region) if plate_region else None
        content = await file.read()
        material = storage_service.save_material(
            category=category,
            filename=file.filename or "video.mp4",
            source_path_or_bytes=content,
            plate_region=norm_region
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
        norm_region = normalize_region_code(payload.plate_region) if payload.plate_region else None
        material = storage_service.save_material(
            category=payload.category,
            filename=p.name,
            source_path_or_bytes=p,
            plate_region=norm_region
        )
        return material
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入本地素材失败: {str(e)}")

@router.patch("/{material_id}/region", response_model=Material)
async def update_material_region(material_id: str, payload: UpdateMaterialRegionRequest):
    """原地修改已入库素材的地区车牌标签"""
    norm_region = normalize_region_code(payload.plate_region) if payload.plate_region else None
    ok = storage_service.update_material_region(material_id, norm_region)
    if not ok:
        raise HTTPException(status_code=404, detail="Material not found")
    m = storage_service.get_material(material_id)
    if not m:
        raise HTTPException(status_code=404, detail="Material not found")
    return m

@router.get("", response_model=List[Material])
async def list_materials(
    category: Optional[MaterialCategory] = None,
    plate_region: Optional[str] = Query(None)
):
    norm_region = normalize_region_code(plate_region) if plate_region else None
    return storage_service.list_materials(category=category, plate_region=norm_region)

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

@router.post("/cleanup")
async def cleanup_materials(dry_run: bool = False):
    """清理素材库：移除测试垃圾/孤儿文件，并按内容哈希自动去重合并重复素材"""
    res = storage_service.cleanup_materials(dry_run=dry_run)
    return {"code": 0, "message": "Cleanup completed successfully", "data": res}
