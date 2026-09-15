import os
from pathlib import Path
from typing import Dict, List

# 基础工作区与存储路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
MATERIALS_DIR = STORAGE_DIR / "materials"
OUTPUTS_DIR = STORAGE_DIR / "outputs"

# 素材分类定义
CATEGORIES: List[str] = ["talking_head", "venue", "medical", "lesson"]
CATEGORY_DIRS: Dict[str, Path] = {
    cat: MATERIALS_DIR / cat for cat in CATEGORIES
}

# 确保所有目录存在
for p in list(CATEGORY_DIRS.values()) + [OUTPUTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# 允许的视频扩展名
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

# 服务端口与主机
SERVER_HOST = os.getenv("VIDEOCUT_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("VIDEOCUT_PORT", "18888"))

# Harness 配置
ACTIVE_HARNESS = os.getenv("ACTIVE_HARNESS", "embedded")  # "embedded", "codex", "zcode"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# 驾校垂直领域高频专有词库（用于 ASR 后校正与关键词精准命中）
DRIVING_SCHOOL_KEYWORDS = {
    "venue": ["训练场", "场地", "五万平", "校区", "考场", "模拟场", "倒车入库区"],
    "medical": ["体检", "视力", "拍照", "面签", "一站式", "体检车", "医院"],
    "lesson": ["练车", "教练", "科目二", "科目三", "科二", "科三", "倒库", "侧方", "坡道", "起步", "打方向", "离合", "刹车"]
}
