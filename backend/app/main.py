from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from app.core.config import STORAGE_DIR, ROOT_DIR

app = FastAPI(
    title="VideoCut Harness API",
    description="Backend service for driving school video cutting with hybrid Harness architecture",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STORAGE_DIR.exists():
    app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

frontend_dist = ROOT_DIR / "frontend" / "dist"
if frontend_dist.exists():
    if (frontend_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    app.mount("/app", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

@app.get("/")
async def root():
    index_path = frontend_dist / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "service": "VideoCut Harness Engine"}

@app.on_event("startup")
def on_startup():
    try:
        from app.db.migrator import migrate_legacy_data
        migrate_legacy_data()
    except Exception as e:
        print(f"[Main] SQLite migration on startup warning: {e}")

@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "service": "VideoCut Harness Engine"}

def mount_routers():
    try:
        from app.api.materials import router as materials_router
        app.include_router(materials_router, prefix="/api/v1/materials", tags=["Materials"])
    except Exception as e:
        print(f"Note: materials router: {e}")

    try:
        from app.api.editor import router as editor_router
        app.include_router(editor_router, prefix="/api/v1/projects", tags=["Projects"])
        app.include_router(editor_router, prefix="/api/v1/editor", tags=["Editor"])
    except Exception as e:
        pass

    try:
        from app.api.instruction import router as instruction_router
        app.include_router(instruction_router, prefix="/api/v1/instruction", tags=["Instruction"])
    except Exception as e:
        pass

    try:
        from app.api.batch import router as batch_router
        app.include_router(batch_router, prefix="/api/v1/batch", tags=["Batch"])
    except Exception as e:
        pass

    try:
        from app.api.system import router as system_router
        app.include_router(system_router, prefix="/api/v1/system", tags=["System"])
    except Exception as e:
        pass

    try:
        from app.api.settings import router as settings_router
        app.include_router(settings_router, prefix="/api/v1/settings", tags=["Settings"])
    except Exception as e:
        pass

    try:
        from app.api.chat import router as chat_router
        app.include_router(chat_router, prefix="/api/v1/chat", tags=["Chat"])
    except Exception as e:
        pass

mount_routers()
