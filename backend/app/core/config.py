import os
from pathlib import Path
from typing import Dict, List

# 基础工作区与存储路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
MATERIALS_DIR = STORAGE_DIR / "materials"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
PROJECTS_DIR = STORAGE_DIR / "projects"

# 素材分类定义
CATEGORIES: List[str] = ["talking_head", "venue", "medical", "lesson"]
CATEGORY_DIRS: Dict[str, Path] = {
    cat: MATERIALS_DIR / cat for cat in CATEGORIES
}

# 确保所有目录存在
for p in list(CATEGORY_DIRS.values()) + [OUTPUTS_DIR, PROJECTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# 允许的视频扩展名
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

# 服务端口与主机
SERVER_HOST = os.getenv("VIDEOCUT_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("VIDEOCUT_PORT", "18888"))

# Harness 配置
ZCODE_CLI_PATH = Path(os.getenv("ZCODE_CLI_PATH", r"D:\Program Files\ZCode\resources\glm\zcode.cjs"))
SETTINGS_FILE = STORAGE_DIR / "settings.json"

def has_zcode_available() -> bool:
    import shutil
    return ZCODE_CLI_PATH.exists() and bool(shutil.which("node"))

def has_codex_available() -> bool:
    import shutil
    return bool(shutil.which("codex"))

def get_codex_configured_model() -> str:
    try:
        cfg_path = Path.home() / ".codex" / "config.toml"
        if cfg_path.exists():
            import tomllib
            with open(cfg_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("model", "")
    except Exception:
        pass
    return ""

def get_codex_provider_config() -> dict:
    """读取 ~/.codex/config.toml 中的代理端点与模型配置"""
    try:
        cfg_path = Path.home() / ".codex" / "config.toml"
        if cfg_path.exists():
            import tomllib
            with open(cfg_path, "rb") as f:
                data = tomllib.load(f)
                model = data.get("model", "glm-5.3-flash")
                provider_name = data.get("model_provider", "custom")
                providers = data.get("model_providers", {})
                prov_cfg = providers.get(provider_name, {})
                base_url = prov_cfg.get("base_url", "http://127.0.0.1:15721/v1")
                token = prov_cfg.get("experimental_bearer_token", "PROXY_MANAGED")
                return {
                    "model": model,
                    "base_url": base_url,
                    "token": token
                }
    except Exception:
        pass
    return {
        "model": "glm-5.3-flash",
        "base_url": "http://127.0.0.1:15721/v1",
        "token": "PROXY_MANAGED"
    }

def get_default_harness() -> str:
    if has_codex_available():
        return "codex"
    if has_zcode_available():
        return "zcode"
    return "embedded"

DEFAULT_HARNESS = get_default_harness()
ACTIVE_HARNESS = os.getenv("ACTIVE_HARNESS", DEFAULT_HARNESS)  # "embedded", "codex", "zcode"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", get_codex_configured_model() or "glm-5.3-flash")

def load_settings():
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    codex_model = get_codex_configured_model()
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                ACTIVE_HARNESS = data.get("active_harness", ACTIVE_HARNESS)
                LLM_API_KEY = data.get("llm_api_key", LLM_API_KEY)
                LLM_BASE_URL = data.get("llm_base_url", LLM_BASE_URL)
                stored_model = data.get("llm_model")
                # 保护机制：如果当前处于 codex 引擎且本地 codex 真实配置了模型，强制对齐真实模型
                if ACTIVE_HARNESS == "codex" and codex_model:
                    LLM_MODEL = codex_model
                else:
                    LLM_MODEL = stored_model or codex_model or "glm-5.3-flash"
        except Exception:
            pass
    elif codex_model:
        LLM_MODEL = codex_model

def save_settings(data: dict):
    import json
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    if "active_harness" in data:
        ACTIVE_HARNESS = data["active_harness"]
    if "llm_api_key" in data:
        LLM_API_KEY = data["llm_api_key"]
    if "llm_base_url" in data:
        LLM_BASE_URL = data["llm_base_url"]
    if "llm_model" in data:
        LLM_MODEL = data["llm_model"]
    
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "active_harness": ACTIVE_HARNESS,
            "llm_api_key": LLM_API_KEY,
            "llm_base_url": LLM_BASE_URL,
            "llm_model": LLM_MODEL
        }, f, ensure_ascii=False, indent=2)

# 初始化读取已有配置
load_settings()

# 驾校垂直领域高频专有词库（用于 ASR 后校正与关键词精准命中）
DRIVING_SCHOOL_KEYWORDS = {
    "venue": ["训练场", "场地", "五万平", "校区", "考场", "模拟场", "倒车入库区"],
    "medical": ["体检", "视力", "拍照", "面签", "一站式", "体检车", "医院"],
    "lesson": ["练车", "教练", "金牌教练", "科目二", "科目三", "科二", "科三", "倒库", "侧方", "坡道", "起步", "打方向", "离合", "刹车"],
    "emphasis": ["一把过", "轻松一把过", "特别方便", "十分钟", "快速搞定", "手把手", "标准化", "自建", "秘籍", "包过", "零基础", "关键点", "必看"]
}
