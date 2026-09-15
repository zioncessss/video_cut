from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid
import time

class MaterialCategory(str, Enum):
    TALKING_HEAD = "talking_head"
    VENUE = "venue"
    MEDICAL = "medical"
    LESSON = "lesson"

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
    broll_material_id: Optional[str] = None
    is_manual_edited: bool = False

class BrollReplacement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float
    end_time: float
    material_id: str
    material_category: MaterialCategory
    playback_mode: str = "fit"  # "fit", "loop", "slow"

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
    status: CutProjectStatus = CutProjectStatus.DRAFT
    output_video_path: Optional[str] = None
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
