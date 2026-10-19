import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

# 基础工作区与存储路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
# 数据根目录可被环境变量注入（sidecar 打包模式由 Electron 主进程指定便携目录）
VIDEOCUT_STORAGE_DIR = os.getenv("VIDEOCUT_STORAGE_DIR", "").strip().strip('"').strip("'")

def _resolve_safe_storage_dir() -> Path:
    base = Path(VIDEOCUT_STORAGE_DIR) if VIDEOCUT_STORAGE_DIR else ROOT_DIR / "storage"
    try:
        base.mkdir(parents=True, exist_ok=True)
        test_f = base / ".write_probe"
        test_f.write_bytes(b"ok")
        test_f.unlink(missing_ok=True)
        return base
    except Exception as e:
        # 当安装目录不可写（例如 Windows 安装到 C:\Program Files 且非管理员权限）时，自愈回退至用户数据安全存储区
        print(f"[Config] 目标存储目录 {base} 不可写 ({e})，自动自愈切换至用户安全存储区...")
        fallback = Path(os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())) / "videocut" / "storage"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

def _heal_and_restore_storage_if_empty(storage_dir: Path) -> None:
    """
    更新防御自愈：当当前 storage 目录为空（如应用更新后被安装包抹除），
    自动从系统安全持久备份区或开发工程目录恢复用户素材、工程和数据库
    """
    db_file = storage_dir / "videocut.db"
    # 如果数据库文件存在且大于 90KB，说明已有用户真实业务数据，无需恢复
    if db_file.exists() and db_file.stat().st_size > 90 * 1024:
        return

    candidates: List[Path] = []
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        persistent_storage = Path(local_app_data) / "videocut_persistent_storage"
        candidates.append(persistent_storage)
        active_ptr = persistent_storage / "active_storage_dir.txt"
        if active_ptr.exists():
            try:
                hist_dir = Path(active_ptr.read_text(encoding="utf-8").strip())
                if hist_dir.exists():
                    candidates.append(hist_dir)
            except Exception:
                pass
        candidates.append(Path(local_app_data) / "videocut" / "storage")
    app_data = os.getenv("APPDATA")
    if app_data:
        candidates.append(Path(app_data) / "videocut" / "storage")

    import sys
    # 注册表与常见历史安装目录探测 (Windows)
    if sys.platform == "win32":
        try:
            import winreg
            for root_k in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root_k, r"Software\videocut") as k:
                        inst_loc = winreg.QueryValueEx(k, "InstallLocation")[0]
                        if inst_loc:
                            candidates.append(Path(inst_loc) / "storage")
                except Exception:
                    pass
        except Exception:
            pass

    if ROOT_DIR:
        candidates.append(ROOT_DIR / "storage")

    if sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "videocut" / "storage")
        candidates.append(Path.home() / ".videocut" / "storage")

    best_candidate: Path | None = None
    max_size = 90 * 1024

    for cand in candidates:
        if not cand.exists() or cand.resolve() == storage_dir.resolve():
            continue
        cand_db = cand / "videocut.db"
        if cand_db.exists():
            s = cand_db.stat().st_size
            if s > max_size:
                max_size = s
                best_candidate = cand

    if best_candidate:
        try:
            import shutil
            print(f"[Config] 检测到当前数据目录为空，自动从数据源 {best_candidate} (DB大小: {max_size//1024}KB) 恢复用户工程与素材...")
            for item in best_candidate.iterdir():
                dst_item = storage_dir / item.name
                if item.is_dir():
                    shutil.copytree(str(item), str(dst_item), dirs_exist_ok=True)
                elif item.is_file():
                    shutil.copy2(str(item), str(dst_item))
            print(f"[Config] 用户数据恢复成功，杜绝更新后视频消失！")

            # 同时也同步一份至独立持久区建立双重保险
            if local_app_data:
                persistent = Path(local_app_data) / "videocut_persistent_storage"
                if best_candidate.resolve() != persistent.resolve():
                    persistent.mkdir(parents=True, exist_ok=True)
                    for item in best_candidate.iterdir():
                        dst_item = persistent / item.name
                        if item.is_dir():
                            shutil.copytree(str(item), str(dst_item), dirs_exist_ok=True)
                        elif item.is_file():
                            shutil.copy2(str(item), str(dst_item))
                    print(f"[Config] 已同步写入持久备份区 {persistent}")
        except Exception as err:
            print(f"[Config] 恢复备份数据失败: {err}")

def _record_active_storage_dir(storage_dir: Path) -> None:
    try:
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            persistent = Path(local_app_data) / "videocut_persistent_storage"
            persistent.mkdir(parents=True, exist_ok=True)
            (persistent / "active_storage_dir.txt").write_text(str(storage_dir.resolve()), encoding="utf-8")
    except Exception:
        pass

STORAGE_DIR = _resolve_safe_storage_dir()
_heal_and_restore_storage_if_empty(STORAGE_DIR)
_record_active_storage_dir(STORAGE_DIR)
MATERIALS_DIR = STORAGE_DIR / "materials"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
PROJECTS_DIR = STORAGE_DIR / "projects"
COVERS_DIR = STORAGE_DIR / "covers"     # 005: 工程封面（截帧/上传）
TASKS_DIR = STORAGE_DIR / "tasks"       # 005-US11: 独立工程文件夹目录（日期+时间）

raw_db_env = os.getenv("VIDEOCUT_DB_PATH", "").strip().strip('"').strip("'")
DB_PATH = Path(raw_db_env) if raw_db_env else (STORAGE_DIR / "videocut.db")

# 素材分类定义（experience 为原 medical 体检分类的扩展升级：学员全流程体验空镜）
CATEGORIES: List[str] = ["talking_head", "venue", "experience", "lesson"]
CATEGORY_DIRS: Dict[str, Path] = {
    cat: MATERIALS_DIR / cat for cat in CATEGORIES
}

# 确保所有目录存在
for p in list(CATEGORY_DIRS.values()) + [OUTPUTS_DIR, PROJECTS_DIR, COVERS_DIR, TASKS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

def create_task_dir(title: str = "clip") -> Path:
    """按 YYYYMMDD_HHMMSS_{safe_title} 创建并返回专属独立工程目录"""
    import datetime
    import re
    safe_title = re.sub(r'[^A-Za-z0-9\u4e00-\u9fff_-]', '_', title)[:32].strip('_') or "clip"
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{ts}_{safe_title}"
    task_path = TASKS_DIR / dir_name
    task_path.mkdir(parents=True, exist_ok=True)
    return task_path

# 允许的视频扩展名
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

# 服务端口与主机
SERVER_HOST = os.getenv("VIDEOCUT_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("VIDEOCUT_PORT", "18888"))

# Harness 配置
ZCODE_CLI_PATH = Path(os.getenv("ZCODE_CLI_PATH", r"D:\Program Files\ZCode\resources\glm\zcode.cjs"))
SETTINGS_FILE = STORAGE_DIR / "settings.json"

def _ensure_mac_tool_paths():
    import sys
    if sys.platform == "darwin":
        mac_paths = ["/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".cargo" / "bin")]
        current = os.environ.get("PATH", "")
        for p in mac_paths:
            if p not in current.split(":") and os.path.exists(p):
                os.environ["PATH"] = f"{p}:{current}"
                current = os.environ["PATH"]

def _download_binary_fallback(bin_name: str) -> Optional[Path]:
    """若随包与系统均无该二进制，尝试静默自愈拉取到 STORAGE_DIR/bin（避开 Program Files 权限限制）"""
    try:
        import platform
        import urllib.request
        
        target_dir = STORAGE_DIR / "bin"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        ext = ".exe" if sys.platform == "win32" else ""
        file_name = f"{bin_name}{ext}"
        dest_path = target_dir / file_name
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            return dest_path
            
        arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
        if sys.platform == "win32":
            url = f"https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/{bin_name}-win32-x64"
        elif sys.platform == "darwin":
            url = f"https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/{bin_name}-darwin-{arch}"
        else:
            return None
            
        print(f"[config] 正在触发底层算力自愈，静默拉取 {bin_name} 到 {dest_path}...")
        urllib.request.urlretrieve(url, str(dest_path))
        if dest_path.exists() and dest_path.stat().st_size > 1024:
            if sys.platform != "win32":
                dest_path.chmod(0o755)
            print(f"[config] 底层算力自愈成功: {dest_path}")
            return dest_path
    except Exception as e:
        print(f"[config] 算力组件 {bin_name} 自愈下载失败: {e}")
    return None

def get_ffmpeg_cmd() -> str:
    """获取可用的 ffmpeg 可执行文件路径"""
    import shutil
    import sys
    
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir.parent / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
        candidates.append(exe_dir / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
        candidates.append(exe_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    
    candidates.append(ROOT_DIR / "resources" / "engine" / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    candidates.append(STORAGE_DIR / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"))
    
    if sys.platform == "win32":
        user_home = Path.home()
        candidates.append(user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe")
        candidates.append(Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"))
        candidates.append(user_home / "scoop" / "shims" / "ffmpeg.exe")
        candidates.append(Path("C:/ffmpeg/bin/ffmpeg.exe"))
    elif sys.platform == "darwin":
        candidates.append(Path("/opt/homebrew/bin/ffmpeg"))
        candidates.append(Path("/usr/local/bin/ffmpeg"))
        
    for cand in candidates:
        if cand.exists():
            bin_dir = str(cand.parent)
            path_sep = ";" if sys.platform == "win32" else ":"
            if bin_dir not in os.environ.get("PATH", "").split(path_sep):
                os.environ["PATH"] = f"{bin_dir}{path_sep}{os.environ.get('PATH', '')}"
            return str(cand)

    found = shutil.which("ffmpeg")
    if found:
        return found
        
    fallback = _download_binary_fallback("ffmpeg")
    if fallback:
        bin_dir = str(fallback.parent)
        path_sep = ";" if sys.platform == "win32" else ":"
        if bin_dir not in os.environ.get("PATH", "").split(path_sep):
            os.environ["PATH"] = f"{bin_dir}{path_sep}{os.environ.get('PATH', '')}"
        return str(fallback)
            
    return "ffmpeg"

def get_ffprobe_cmd() -> str:
    """获取可用的 ffprobe 可执行文件路径"""
    import shutil
    import sys
    
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir.parent / "bin" / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
        candidates.append(exe_dir / "bin" / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
        candidates.append(exe_dir / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
    
    candidates.append(ROOT_DIR / "resources" / "engine" / "bin" / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
    candidates.append(STORAGE_DIR / "bin" / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe"))
    
    if sys.platform == "win32":
        user_home = Path.home()
        candidates.append(user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe")
        candidates.append(Path("C:/ProgramData/chocolatey/bin/ffprobe.exe"))
        candidates.append(user_home / "scoop" / "shims" / "ffprobe.exe")
        candidates.append(Path("C:/ffmpeg/bin/ffprobe.exe"))
    elif sys.platform == "darwin":
        candidates.append(Path("/opt/homebrew/bin/ffprobe"))
        candidates.append(Path("/usr/local/bin/ffprobe"))
        
    for cand in candidates:
        if cand.exists():
            bin_dir = str(cand.parent)
            path_sep = ";" if sys.platform == "win32" else ":"
            if bin_dir not in os.environ.get("PATH", "").split(path_sep):
                os.environ["PATH"] = f"{bin_dir}{path_sep}{os.environ.get('PATH', '')}"
            return str(cand)

    found = shutil.which("ffprobe")
    if found:
        return found

    fallback = _download_binary_fallback("ffprobe")
    if fallback:
        bin_dir = str(fallback.parent)
        path_sep = ";" if sys.platform == "win32" else ":"
        if bin_dir not in os.environ.get("PATH", "").split(path_sep):
            os.environ["PATH"] = f"{bin_dir}{path_sep}{os.environ.get('PATH', '')}"
        return str(fallback)
            
    return "ffprobe"

def has_zcode_available() -> bool:
    _ensure_mac_tool_paths()
    import shutil
    return ZCODE_CLI_PATH.exists() and bool(shutil.which("node"))

def has_codex_available() -> bool:
    _ensure_mac_tool_paths()
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

ASR_PROVIDER = os.getenv("ASR_PROVIDER", "minimax")  # "minimax" | "local"
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")

def get_minimax_api_key() -> str:
    """获取 MiniMax API Key（优先独立 minimax_api_key，未配置则复用 llm_api_key）"""
    return (os.getenv("MINIMAX_API_KEY", "").strip() or MINIMAX_API_KEY or LLM_API_KEY or "").strip()

def get_minimax_base_url() -> str:
    """获取 MiniMax API 根地址"""
    url = os.getenv("MINIMAX_BASE_URL", "").strip() or MINIMAX_BASE_URL
    if not url:
        if "minimax" in (LLM_BASE_URL or "").lower():
            url = LLM_BASE_URL
        else:
            url = "https://api.minimaxi.com/v1"
    return url.rstrip("/")

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
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROTOCOL, ASR_PROVIDER, MINIMAX_API_KEY, MINIMAX_BASE_URL
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
                ASR_PROVIDER = data.get("asr_provider", ASR_PROVIDER)
                MINIMAX_API_KEY = data.get("minimax_api_key", MINIMAX_API_KEY)
                MINIMAX_BASE_URL = data.get("minimax_base_url", MINIMAX_BASE_URL)
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
    global ACTIVE_HARNESS, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROTOCOL, ASR_PROVIDER, MINIMAX_API_KEY, MINIMAX_BASE_URL
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
    if "asr_provider" in data:
        ASR_PROVIDER = data["asr_provider"]
    if "minimax_api_key" in data:
        MINIMAX_API_KEY = data["minimax_api_key"]
    if "minimax_base_url" in data:
        MINIMAX_BASE_URL = data["minimax_base_url"]

    settings_file = _ensure_storage_path(SETTINGS_FILE)
    payload = {
        "active_harness": ACTIVE_HARNESS,
        "llm_api_key": LLM_API_KEY,
        "llm_base_url": LLM_BASE_URL,
        "llm_model": LLM_MODEL,
        "llm_protocol": LLM_PROTOCOL,
        "asr_provider": ASR_PROVIDER
    }
    if MINIMAX_API_KEY:
        payload["minimax_api_key"] = MINIMAX_API_KEY
    if MINIMAX_BASE_URL and MINIMAX_BASE_URL != "https://api.minimaxi.com/v1":
        payload["minimax_base_url"] = MINIMAX_BASE_URL

    settings_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

# 初始化读取已有配置
load_settings()

# 专用业务词库与 ASR 纠偏知识库配置文件路径
GLOSSARY_FILE = STORAGE_DIR / "glossary.json"

def resolve_media_path(raw_path: Optional[Union[str, Path]]) -> Optional[Path]:
    """
    全系统权威媒体与工程路径解析器。
    无论路径格式为：
    - 数据库标准相对路径: "storage/materials/talking_head/xyz.mp4" 或 "storage/tasks/abc/subtitles.ass"
    - 无 storage 前缀相对路径: "materials/talking_head/xyz.mp4" 或 "tasks/abc/video.mp4"
    - 存量绝对路径（可能来自旧安装目录、旧机器盘符、或开发机 D:/project/...）
    - 外部上传文件绝对路径
    统一自愈解析为当前环境实际有效的物理 Path。
    """
    if not raw_path:
        return None

    raw_str = str(raw_path).strip().strip('"').strip("'")
    if not raw_str:
        return None

    norm_str = raw_str.replace("\\", "/")
    p = Path(raw_str)

    # 1. 本身是绝对路径且在当前系统上物理存在，直接返回
    try:
        if p.is_absolute() and p.exists():
            return p.resolve()
    except Exception:
        pass

    # 2. 如果是绝对路径但不存在（说明来自更新前旧目录或不同机器的绝对路径）
    # 提取 storage/ 后面的相对部分，尝试在当前 STORAGE_DIR 中对齐
    storage_prefix = f"{STORAGE_DIR.name}/"
    markers = (storage_prefix, "storage/", "materials/", "tasks/", "outputs/", "covers/")
    sub_rel = None
    for marker in markers:
        if marker in norm_str:
            idx = norm_str.find(marker)
            sub_rel = norm_str[idx:]
            break

    candidates_to_check: List[Path] = []
    if sub_rel:
        clean_rel = sub_rel
        for pref in (storage_prefix, "storage/"):
            if clean_rel.startswith(pref):
                clean_rel = clean_rel[len(pref):]
                break
        candidates_to_check.append(STORAGE_DIR / clean_rel)
        candidates_to_check.append(STORAGE_DIR.parent / sub_rel)

    # 3. 标准相对路径判定
    if not p.is_absolute():
        candidates_to_check.append(STORAGE_DIR.parent / raw_str)
        candidates_to_check.append(STORAGE_DIR / raw_str)
        for pref in (storage_prefix, "storage/"):
            if norm_str.startswith(pref):
                candidates_to_check.append(STORAGE_DIR / norm_str[len(pref):])

    # 4. 跨版本持久备份区与历史存储目录探查
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        persistent_storage = Path(local_app_data) / "videocut_persistent_storage"
        if persistent_storage.exists():
            if sub_rel:
                clean_rel = sub_rel
                for pref in (storage_prefix, "storage/"):
                    if clean_rel.startswith(pref):
                        clean_rel = clean_rel[len(pref):]
                        break
                candidates_to_check.append(persistent_storage / clean_rel)
            elif not p.is_absolute():
                candidates_to_check.append(persistent_storage / raw_str)
            active_ptr = persistent_storage / "active_storage_dir.txt"
            if active_ptr.exists():
                try:
                    hist_dir = Path(active_ptr.read_text(encoding="utf-8").strip())
                    if hist_dir.exists() and hist_dir.resolve() != STORAGE_DIR.resolve():
                        if sub_rel:
                            clean_rel = sub_rel
                            for pref in (storage_prefix, "storage/"):
                                if clean_rel.startswith(pref):
                                    clean_rel = clean_rel[len(pref):]
                                    break
                            candidates_to_check.append(hist_dir / clean_rel)
                        elif not p.is_absolute():
                            candidates_to_check.append(hist_dir / raw_str)
                except Exception:
                    pass

    for cand in candidates_to_check:
        try:
            if cand.exists():
                return cand.resolve()
        except Exception:
            continue

    # 若物理文件尚未生成（如新任务的 output_video_path 目标路径），返回标准 STORAGE_DIR 映射路径
    if sub_rel:
        clean_rel = sub_rel
        for pref in (storage_prefix, "storage/"):
            if clean_rel.startswith(pref):
                clean_rel = clean_rel[len(pref):]
                break
        return (STORAGE_DIR / clean_rel).resolve()
    if not p.is_absolute():
        return (STORAGE_DIR.parent / raw_str).resolve()
    return p.resolve()


def to_storage_relative(path: Optional[Union[str, Path]]) -> str:
    """
    统一将任意物理路径转换为相对于 STORAGE_DIR.parent 的标准相对路径
    (生产环境下为 'storage/tasks/...'，测试环境下为 'videocut_pytest_storage/tasks/...')
    保证与 STORAGE_DIR.parent 互逆兼容，无论测试还是生产环境均不漂移
    """
    if not path:
        return ""
    storage_folder_name = STORAGE_DIR.name
    try:
        p = Path(path).resolve()
        if p == STORAGE_DIR.resolve() or STORAGE_DIR.resolve() in p.parents:
            return str(p.relative_to(STORAGE_DIR.parent)).replace("\\", "/")
    except Exception:
        pass

    norm_str = str(path).replace("\\", "/").strip()
    if f"/{storage_folder_name}/" in norm_str:
        return f"{storage_folder_name}/" + norm_str.split(f"/{storage_folder_name}/", 1)[1]
    if norm_str.startswith(f"{storage_folder_name}/"):
        return norm_str

    if "/storage/" in norm_str:
        rel_tail = norm_str.split("/storage/", 1)[1]
        return f"{storage_folder_name}/{rel_tail}"
    if norm_str.startswith("storage/"):
        return f"{storage_folder_name}/" + norm_str[len("storage/"):]

    for marker in ("materials/", "tasks/", "outputs/", "covers/"):
        if marker in norm_str:
            return f"{storage_folder_name}/" + norm_str[norm_str.find(marker):]

    return norm_str


def _ensure_storage_path(path: Path) -> Path:
    """
    规范化路径并校验或自愈其位于 storage 目录内。
    若路径来自旧安装路径或迁移源，自动自愈重映射至当前 STORAGE_DIR。
    """
    resolved = path.resolve()
    # 如果已在 STORAGE_DIR 内，直接放行
    if resolved == STORAGE_DIR.resolve() or STORAGE_DIR.resolve() in resolved.parents:
        return resolved

    # 尝试自愈：如果在当前 STORAGE_DIR 中存在同名相对路径，自动重定向
    cand = resolve_media_path(resolved)
    if cand and cand.exists():
        return cand

    # 如果是本地存在的合法物理文件（如用户上传的外部自定义封面），直接放行
    if resolved.exists():
        return resolved

    return resolved


# 供各存储/合成模块统一复用的公开守卫入口
ensure_storage_path = _ensure_storage_path

_GLOSSARY_CACHE: Dict[str, object] = {"mtime": None, "data": None}

def _seed_default_glossary_if_missing(dest: Path) -> None:
    """若 storage/glossary.json 不存在，从系统/打包自带的模板词库复制初始化"""
    if dest.exists():
        return
    import sys
    candidates = [
        ROOT_DIR / "storage" / "glossary.json",
        Path(__file__).resolve().parent.parent.parent.parent / "storage" / "glossary.json"
    ]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.extend([
            exe_dir.parent / "default_storage" / "glossary.json",
            exe_dir.parent.parent / "resources" / "default_storage" / "glossary.json",
            exe_dir / "default_storage" / "glossary.json"
        ])
    for cand in candidates:
        if cand.exists() and cand.resolve() != dest.resolve():
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copyfile(str(cand), str(dest))
                print(f"[Config] 已自动从 {cand} 初始挂载词库到 {dest}")
                break
            except Exception as e:
                print(f"[Config] 初始挂载词库失败: {e}")

def load_glossary() -> dict:
    """动态读取本地词库与纠错配置文件，按 mtime 缓存：编辑文件后立即生效，无需重启"""
    glossary_file = _ensure_storage_path(GLOSSARY_FILE)
    if not glossary_file.exists():
        _seed_default_glossary_if_missing(glossary_file)
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

def reset_glossary_to_default() -> dict:
    """重置 glossary.json 为系统默认模板"""
    glossary_file = _ensure_storage_path(GLOSSARY_FILE)
    if glossary_file.exists():
        glossary_file.unlink(missing_ok=True)
    _seed_default_glossary_if_missing(glossary_file)
    _GLOSSARY_CACHE["mtime"] = None
    _GLOSSARY_CACHE["data"] = None
    return load_glossary()

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

