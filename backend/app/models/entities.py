from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
import time

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

class SubtitleSegment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float
    end_time: float
    raw_text: str
    corrected_text: str
    matched_category: Optional[MaterialCategory] = None
    matched_keywords: List[str] = Field(default_factory=list)
    highlight_words: List[HighlightWord] = Field(default_factory=list)
    scene_decision: Optional[SceneDecision] = None
    broll_material_id: Optional[str] = None
    is_manual_edited: bool = False

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
    subtitle_font_size: Optional[int] = None # 自定义连续字号 (24~96px)
    show_subtitles: bool = True
    subtitle_position_y: int = 82       # 竖屏垂直百分比 10~95% (默认82%黄金底部)
    subtitle_position_x: int = 50       # 竖屏水平百分比 5~95% (默认50%居中)
    subtitle_width_percent: Optional[int] = None # 自定义字幕最大宽度百分比 30~95%
    enable_highlight: bool = True
    highlight_color: str = "#FACC15"
    highlight_scale: bool = True
    custom_highlight_words: List[str] = Field(default_factory=list)
    transition_style: str = "cut"       # cut(硬切) | fade(叠化 0.3~0.5s，时长取各句 scene_decision)
    
    enable_top_banner: bool = True
    banner_main_title: str = "科目二一把过秘籍"
    banner_sub_title: Optional[str] = "教练手把手教学"
    banner_style: str = "capsule"       # capsule, full_width
    banner_size: str = "medium"         # small, medium, large
    banner_font_size: Optional[int] = None # 自定义字号 (24~72px)
    banner_width_percent: Optional[int] = None # 自定义横幅宽度百分比 20~95%
    banner_position_x: int = 50         # 水平百分比 5~95% (默认50%居中)
    banner_position_y: int = 6          # 垂直百分比 2~85% (默认6%顶部)
    
    enable_watermark: bool = True
    watermark_text: str = "@顺达驾校官方教学"
    watermark_position: str = "top_right"  # top_right, top_left, bottom_right, bottom_left
    watermark_size: str = "medium"         # small, medium, large
    watermark_font_size: Optional[int] = None # 自定义字号 (14~60px)
    watermark_position_x: Optional[int] = None # 水平微调百分比 2~98%
    watermark_position_y: Optional[int] = None # 垂直微调百分比 2~98%
    watermark_opacity: float = 0.4
    
    broll_pacing: str = "standard"      # fast, standard, talking_only

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
    output_video_path: Optional[str] = None
    output_absolute_path: Optional[str] = None
    output_filename: Optional[str] = None
    output_file_size_mb: Optional[float] = None
    raw_asr_segments: Optional[List[Dict[str, Any]]] = None
    corrections_summary: Optional[List[Dict[str, Any]]] = None
    pipeline_notes: Optional[Dict[str, Any]] = None
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

class BatchJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_count: int
    completed_count: int = 0
    concurrency: int = 2
    status: BatchJobStatus = BatchJobStatus.QUEUED
    created_at: float = Field(default_factory=time.time)

class PipelineStage(str, Enum):
    IDLE = "idle"
    AUDIO_EXTRACTING = "audio_extracting"   # 15%
    ASR_TRANSCRIBING = "asr_transcribing"   # 50%
    LLM_CORRECTING = "llm_correcting"       # 75%
    SCENE_DECIDING = "scene_deciding"       # 82% AI 分镜决策
    BROLL_MATCHING = "broll_matching"       # 90%
    COMPLETED = "completed"                 # 100%
    FAILED = "failed"

class PipelineProgress(BaseModel):
    project_id: str
    stage: PipelineStage = PipelineStage.IDLE
    percent: int = 0
    message: str = ""
    updated_at: float = Field(default_factory=time.time)

