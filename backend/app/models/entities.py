from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
import time

class ASRProvider(str, Enum):
    MINIMAX = "minimax"
    LOCAL = "local"

class SubtitleWord(BaseModel):
    word: str
    start: float
    end: float

class MaterialCategory(str, Enum):
    TALKING_HEAD = "talking_head"
    VENUE = "venue"
    EXPERIENCE = "experience"   # 体验空镜（原 medical 体检，扩展为学员全流程体验）
    LESSON = "lesson"

class HighlightWordSource(str, Enum):
    GLOSSARY = "glossary"
    AI = "ai"
    MANUAL = "manual"

class HighlightWord(BaseModel):
    word: str
    source: str = "glossary"  # glossary | ai | manual
    color: Optional[str] = "#FACC15"  # 高亮颜色（如 #38BDF8 蓝色地名、#EF4444 红色费用、#FFFFFF 白色高亮、#FACC15 金黄考点）
    category: Optional[str] = None  # location | price | exam | white | emphasis

class SceneDecision(BaseModel):
    """AI 分镜决策结果：part 用于叙事分段与不切区校验，broll_category=None 表示不切"""
    part: str = "body"  # hook | body | cta
    broll_category: Optional[MaterialCategory] = None
    broll_duration: float = 0.0
    transition_seconds: float = 0.0
    material_id: Optional[str] = None
    reason: str = ""

class Material(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: MaterialCategory
    filename: str
    filepath: str
    duration: float = 0.0
    width: int = 1080
    height: int = 1920
    fps: float = 30.0
    created_at: float = Field(default_factory=time.time)

class PruneReason(str, Enum):
    HEAD_IDLE = "head_idle"
    TAIL_IDLE = "tail_idle"
    RETAKE_DISCARD = "retake_discard"
    MID_SILENCE = "mid_silence"
    MANUAL = "manual"

class PruneSpan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float
    end_time: float
    reason: str = "head_idle"
    source_subtitle_id: Optional[str] = None
    target_subtitle_id: Optional[str] = None
    duration: float = 0.0
    is_active: bool = True

class KeptSpan(BaseModel):
    start_time: float
    end_time: float
    duration: float = 0.0
    audio_fade: bool = True

class SubtitleSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float
    end_time: float
    raw_text: str
    corrected_text: str
    matched_category: Optional[MaterialCategory] = None
    matched_keywords: List[str] = Field(default_factory=list)
    highlight_words: List[HighlightWord] = Field(default_factory=list)
    words: List[SubtitleWord] = Field(default_factory=list)
    scene_decision: Optional[SceneDecision] = None
    broll_material_id: Optional[str] = None
    is_manual_edited: bool = False
    is_pruned: bool = False
    prune_reason: Optional[str] = None
    prune_span_id: Optional[str] = None

class BrollReplacement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float
    end_time: float
    material_id: str
    material_category: MaterialCategory
    playback_mode: str = "fit"  # "fit", "loop", "slow"

class EditingStrategy(BaseModel):
    subtitle_theme: str = "glow_gold"   # glow_gold, glass_clean, cinema_shadow, tech_emerald, viral_gold, marker_pen
    font_size: str = "medium"           # small, medium, large, xlarge
    subtitle_font_family: str = "notoserif" # notoserif (思源/华文中宋), kaiti (书法楷体), fangsong (清雅仿宋), songti (经典宋体), yahei (现代黑体)
    subtitle_font_size: Optional[int] = None # 自定义连续字号 (24~96px)
    show_subtitles: bool = True
    subtitle_position_y: int = 74       # 竖屏垂直百分比 10~95% (推荐 74% 黄金舒适区，避开人脸与底部控制条)
    subtitle_position_x: int = 50       # 竖屏水平百分比 5~95% (默认50%居中)
    subtitle_width_percent: Optional[int] = 100 # 自定义字幕最大宽度百分比 (锁定 100%)
    enable_highlight: bool = True
    highlight_color: str = "#FACC15"
    highlight_scale: bool = True
    custom_highlight_words: List[str] = Field(default_factory=list)
    transition_style: str = "cut"       # cut(硬切) | fade(叠化 0.3~0.5s，时长取各句 scene_decision)
    
    enable_top_banner: bool = False   # 默认关闭：用户按需开启
    banner_main_title: str = ""
    banner_sub_title: Optional[str] = ""
    banner_style: str = "capsule"       # capsule, full_width
    banner_size: str = "medium"         # small, medium, large
    banner_font_size: Optional[int] = None # 自定义字号 (24~72px)
    banner_width_percent: Optional[int] = None # 自定义横幅宽度百分比 20~95%
    banner_position_x: int = 50         # 水平百分比 5~95% (默认50%居中)
    banner_position_y: int = 6          # 垂直百分比 2~85% (默认6%顶部)
    
    enable_watermark: bool = False    # 默认关闭：用户输入有效文本并开启时才生效
    watermark_text: str = ""          # 默认空串：未填写时不开启亦不保存虚假文案
    watermark_position: str = "top_right"  # top_right, top_left, bottom_right, bottom_left
    watermark_size: str = "medium"         # small, medium, large
    watermark_font_size: Optional[int] = None # 自定义字号 (14~60px)
    watermark_position_x: Optional[int] = None # 水平微调百分比 2~98%
    watermark_position_y: Optional[int] = None # 垂直微调百分比 2~98%
    watermark_opacity: float = 0.4
    
    broll_pacing: str = "standard"      # fast, standard, talking_only
    broll_target_coverage: float = 0.65 # 目标成片空镜覆盖率 (40%~70% 黄金区间，默认 65%)
    video_speed: float = 1.0            # 视频剪辑倍速 (0.75~2.0，短视频推荐: 1.1x 微快, 1.2x 紧凑)

    # 009: 智能粗剪与气口保留配置
    enable_auto_prune: bool = True
    enable_head_prune: bool = True
    enable_tail_prune: bool = True
    enable_retake_prune: bool = True
    enable_mid_silence_prune: bool = True
    head_padding_seconds: float = 0.10
    tail_padding_seconds: float = 0.12
    mid_silence_threshold: float = 0.90
    mid_silence_breath_gap: float = 0.20
    retake_pause_min: float = 0.40
    retake_similarity_min: float = 0.60

    # 010: 真实人物口播画质调优与滤镜预设
    filter_preset: str = "clean_natural"  # clean_natural (自然通透·推荐), crisp_hd (质感超清), warm_radiant (元气暖肤), original (原色无滤镜)
    filter_strength: float = 1.0          # 滤镜强度 0.0 ~ 1.0 (默认 1.0，0.0 为完全无额外调色)

class BrollCueItem(BaseModel):
    """大模型稀疏分镜切入指示项"""
    start_time: float
    end_time: float
    category: MaterialCategory
    visual_intent: str = ""

class BrollCueResponse(BaseModel):
    """分镜决策顶层响应对象"""
    broll_cues: List[BrollCueItem] = Field(default_factory=list)

class CutProjectStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class CutProject(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    talking_head_id: str
    aspect_ratio: str = "9:16"
    subtitles: List[SubtitleSegment] = Field(default_factory=list)
    broll_replacements: List[BrollReplacement] = Field(default_factory=list)
    strategy: EditingStrategy = Field(default_factory=EditingStrategy)
    status: CutProjectStatus = CutProjectStatus.DRAFT
    prune_spans: List[PruneSpan] = Field(default_factory=list)
    compact_subtitles: Optional[List[SubtitleSegment]] = None
    output_video_path: Optional[str] = None
    output_absolute_path: Optional[str] = None
    output_filename: Optional[str] = None
    output_file_size_mb: Optional[float] = None
    raw_asr_segments: Optional[List[Dict[str, Any]]] = None
    corrections_summary: Optional[List[Dict[str, Any]]] = None
    pipeline_notes: Optional[Dict[str, Any]] = None
    task_dir: Optional[str] = None  # 005-US11: 独立工程文件夹目录（日期+时间）
    cover_image_path: Optional[str] = None
    cover_source: Optional[str] = None  # frame | upload | ai（ai 为规划中占位）
    last_engine_used: Optional[str] = None
    correction_latency_ms: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class HardwareMetrics(BaseModel):
    cpu_cores: int
    cpu_percent: float
    memory_total_gb: float
    memory_available_gb: float
    gpu_accelerator_detected: Optional[str] = None  # "nvenc", "videotoolbox", "qsv", None
    recommended_concurrency: int = 2

class BatchJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"

class BatchJobItem(BaseModel):
    material_id: str
    project_id: Optional[str] = None
    status: str = "queued"  # queued | running | completed | failed
    error: Optional[str] = None
    progress: int = 0
    task_dir: Optional[str] = None
    output_video_path: Optional[str] = None
    output_absolute_path: Optional[str] = None
    cover_image_path: Optional[str] = None
    filename: Optional[str] = None
    duration: Optional[float] = None

class BatchJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_count: int
    completed_count: int = 0
    concurrency: int = 2
    status: BatchJobStatus = BatchJobStatus.QUEUED
    items: List[BatchJobItem] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

class PipelineStage(str, Enum):
    IDLE = "idle"
    AUDIO_EXTRACTING = "audio_extracting"   # 15%
    ASR_TRANSCRIBING = "asr_transcribing"   # 50%
    LLM_CORRECTING = "llm_correcting"       # 75%
    SCENE_DECIDING = "scene_deciding"       # 82% AI 分镜决策
    BROLL_MATCHING = "broll_matching"       # 90%
    VIDEO_COMPOSING = "video_composing"     # 95% 成片压制合成
    COMPLETED = "completed"                 # 100%
    FAILED = "failed"

class PipelineProgress(BaseModel):
    project_id: str
    stage: PipelineStage = PipelineStage.IDLE
    percent: int = 0
    message: str = ""
    updated_at: float = Field(default_factory=time.time)

class EngineSettings(BaseModel):
    active_harness: str = "api"
    llm_model: str = "MiniMax-Text-01"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_protocol: str = "openai"
    asr_provider: str = ASRProvider.MINIMAX.value

class SettingsResponse(BaseModel):
    active_harness: str
    llm_model: str
    llm_api_key_masked: str
    llm_api_key_configured: bool
    llm_base_url: Optional[str] = None
    llm_protocol: str = "openai"
    asr_provider: str = ASRProvider.MINIMAX.value
    detected_engines: Dict[str, bool] = Field(default_factory=dict)
    engine_config: Dict[str, Any] = Field(default_factory=dict)
    zcode_path: Optional[str] = None

