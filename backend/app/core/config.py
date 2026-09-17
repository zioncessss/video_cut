import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# 基础工作区与存储路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
MATERIALS_DIR = STORAGE_DIR / "materials"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
PROJECTS_DIR = STORAGE_DIR / "projects"
COVERS_DIR = STORAGE_DIR / "covers"     # 005: 工程封面（截帧/上传）
DB_PATH = Path(os.getenv("VIDEOCUT_DB_PATH", str(STORAGE_DIR / "videocut.db")))

# 素材分类定义（experience 为原 medical 体检分类的扩展升级：学员全流程体验空镜）
CATEGORIES: List[str] = ["talking_head", "venue", "experience", "lesson"]
CATEGORY_DIRS: Dict[str, Path] = {
    cat: MATERIALS_DIR / cat for cat in CATEGORIES
}

# 确保所有目录存在
for p in list(CATEGORY_DIRS.values()) + [OUTPUTS_DIR, PROJECTS_DIR, COVERS_DIR]:
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

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", get_codex_configured_model() or "glm-5.3-flash")
LLM_PROTOCOL = os.getenv("LLM_PROTOCOL", "openai")  # 直连协议：openai（兼容 /chat/completions）；anthropic/gemini 预留

def get_default_harness() -> str:
    # 默认链：直连大模型 API 可解析（设置项或 codex 本地配置）时优先 api，字幕等固定格式任务最高效
    if LLM_API_KEY or get_codex_provider_config().get("base_url"):
        return "api"
    if has_codex_available():
        return "codex"
    if has_zcode_available():
        return "zcode"
    return "embedded"

DEFAULT_HARNESS = get_default_harness()
ACTIVE_HARNESS = os.getenv("ACTIVE_HARNESS", DEFAULT_HARNESS)  # "api", "embedded", "codex", "zcode"

def load_settings():
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROTOCOL
    codex_model = get_codex_configured_model()
    if SETTINGS_FILE.exists():
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                ACTIVE_HARNESS = data.get("active_harness", ACTIVE_HARNESS)
                LLM_API_KEY = data.get("llm_api_key", LLM_API_KEY)
                LLM_BASE_URL = data.get("llm_base_url", LLM_BASE_URL)
                LLM_PROTOCOL = data.get("llm_protocol", LLM_PROTOCOL)
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
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROTOCOL
    if "active_harness" in data:
        ACTIVE_HARNESS = data["active_harness"]
    if "llm_api_key" in data:
        LLM_API_KEY = data["llm_api_key"]
    if "llm_base_url" in data:
        LLM_BASE_URL = data["llm_base_url"]
    if "llm_model" in data:
        LLM_MODEL = data["llm_model"]
    if "llm_protocol" in data:
        LLM_PROTOCOL = data["llm_protocol"]

    settings_file = _ensure_storage_path(SETTINGS_FILE)
    settings_file.write_text(json.dumps({
        "active_harness": ACTIVE_HARNESS,
        "llm_api_key": LLM_API_KEY,
        "llm_base_url": LLM_BASE_URL,
        "llm_model": LLM_MODEL,
        "llm_protocol": LLM_PROTOCOL
    }, ensure_ascii=False, indent=2), encoding="utf-8")

# 初始化读取已有配置
load_settings()

# 专用业务词库与 ASR 纠偏知识库配置文件路径
GLOSSARY_FILE = STORAGE_DIR / "glossary.json"

def _ensure_storage_path(path: Path) -> Path:
    """规范化路径并校验其必须位于 storage 目录内，杜绝路径穿越"""
    resolved = path.resolve()
    if resolved != STORAGE_DIR.resolve() and STORAGE_DIR.resolve() not in resolved.parents:
        raise ValueError(f"路径越界，仅允许访问 {STORAGE_DIR} 目录内的文件: {path}")
    return resolved

# 供各存储/合成模块统一复用的公开守卫入口
ensure_storage_path = _ensure_storage_path

_GLOSSARY_CACHE: Dict[str, object] = {"mtime": None, "data": None}

def load_glossary() -> dict:
    """动态读取本地词库与纠错配置文件，按 mtime 缓存：编辑文件后立即生效，无需重启"""
    glossary_file = _ensure_storage_path(GLOSSARY_FILE)
    try:
        mtime = glossary_file.stat().st_mtime if glossary_file.exists() else None
    except OSError:
        mtime = None
    if mtime is not None and _GLOSSARY_CACHE["mtime"] == mtime and _GLOSSARY_CACHE["data"] is not None:
        return _GLOSSARY_CACHE["data"]

    data = None
    if glossary_file.exists():
        try:
            with open(glossary_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Config] 读取词库配置文件失败: {e}")
    if not isinstance(data, dict):
        # 真实执行铁律：词库缺失/损坏时兜底必须为空并显式告警，严禁静默注入预置业务文案
        print(f"[Config] 警告: 词库文件 {glossary_file} 缺失或格式非法，纠偏链路将以空词库运行（无纠偏/无热词/无高亮）。请检查 storage/glossary.json")
        data = {
            "location": {},
            "protected_words": [],
            "common_corrections": {},
            "keywords": {}
        }
    _GLOSSARY_CACHE["mtime"] = mtime
    _GLOSSARY_CACHE["data"] = data
    return data

def save_glossary(data: dict) -> dict:
    """持久化保存词库配置并立即刷新缓存"""
    glossary_file = _ensure_storage_path(GLOSSARY_FILE)
    glossary_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _GLOSSARY_CACHE["mtime"] = None
    _GLOSSARY_CACHE["data"] = None
    return data

def get_common_corrections() -> Dict[str, str]:
    """词库纠错映射，错词按长度倒序排列，防止'福州驾校'先被更短的'福州'规则截断替换"""
    corrections = load_glossary().get("common_corrections") or {}
    return {
        str(k): str(v)
        for k, v in sorted(corrections.items(), key=lambda kv: len(str(kv[0])), reverse=True)
        if str(k)
    }

def get_protected_words() -> List[str]:
    """受保护词：讲者真实口语用词，任何纠偏环节不得改写（如'老师'严禁改为'教练'）"""
    return [str(w) for w in (load_glossary().get("protected_words") or [])]

def apply_glossary_corrections(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """按词库对文本做确定性纠偏（幂等，可安全重复调用），返回 (纠偏后文本, 变更明细)"""
    new_text = text or ""
    changes: List[Dict[str, str]] = []
    for typo, correct in get_common_corrections().items():
        if typo in new_text:
            new_text = new_text.replace(typo, correct)
            changes.append({"from": typo, "to": correct, "reason": "词库确定性纠偏"})
    return new_text, changes

def get_asr_initial_prompt(max_chars: int = 200) -> str:
    """由词库生成 ASR initial_prompt：识别阶段即引导模型输出正确专名词，从源头减少错字"""
    glossary = load_glossary()
    loc = glossary.get("location") or {}
    hint = str(loc.get("prompt_hint", "")).strip()
    terms = [str(loc.get("driving_school", "")).strip(), str(loc.get("city", "")).strip()]
    terms += [str(v).strip() for v in (glossary.get("common_corrections") or {}).values()]
    vocab = "、".join(dict.fromkeys(t for t in terms if t))
    prompt = f"{hint} 高频词：{vocab}".strip()
    return prompt[:max_chars]

def get_driving_school_keywords() -> dict:
    """从词库中实时装载分类关键词；词库缺失时返回空表（显性无匹配），不再内嵌预置词表"""
    glossary = load_glossary()
    return glossary.get("keywords") or {}

