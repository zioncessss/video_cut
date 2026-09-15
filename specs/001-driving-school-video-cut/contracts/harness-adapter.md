# Harness 适配器接口协议 (Harness Adapter Contract)

**Version**: 1.0.0  
**Interface Type**: Backend / Engine Decoupling Layer  

---

## 1. 目标与定位

为实现宪章第 II 条“Harness 抽象与引擎解耦”，本项目通过 `BaseHarnessAdapter` 定义统一契约。无论是本地内置的 Python+FFmpeg 执行器，还是外部的 `codex` 或 `zcode` harness 服务，均必须实现此协议。

---

## 2. 接口定义 (Python Abstract Base Class)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class VideoCutRequest(BaseModel):
    project_id: str
    talking_head_path: str
    target_aspect_ratio: str = "9:16"  # "9:16" or "16:9"
    subtitles: List[Dict[str, Any]]
    broll_cutaways: List[Dict[str, Any]]
    burn_subtitles: bool = True
    output_dir: str

class TaskProgress(BaseModel):
    task_id: str
    stage: str  # "extract_audio" | "asr" | "llm_correct" | "broll_compose" | "ffmpeg_render"
    progress_percent: float
    message: str

class HardwareMetrics(BaseModel):
    cpu_percent: float
    memory_available_gb: float
    gpu_accelerator_detected: Optional[str] = None  # "nvenc" | "videotoolbox" | "qsv" | None
    recommended_concurrency: int = 2

class BaseHarnessAdapter(ABC):
    @abstractmethod
    async def get_capabilities(self) -> Dict[str, Any]:
        """返回当前 Harness 具备的能力（例如：本地硬件加速、支持的模型版本等）"""
        pass

    @abstractmethod
    async def inspect_resources(self) -> HardwareMetrics:
        """获取当前宿主机硬件资源与推荐并发配额"""
        pass

    @abstractmethod
    async def transcribe_and_correct(self, audio_path: str) -> List[Dict[str, Any]]:
        """执行 ASR 识别 + LLM 语义校偏，返回时间戳字幕序列"""
        pass

    @abstractmethod
    async def render_video(self, request: VideoCutRequest, progress_callback=None) -> str:
        """根据切片工程配置驱动 FFmpeg 管道执行渲染，返回输出视频路径"""
        pass
```

---

## 3. 外部 Harness (Codex / ZCode) 扩展规范

若切换至 Codex 或 ZCode Harness：
1. 建立 `CodexHarnessAdapter` 实现类。
2. 将 `VideoCutRequest` 映射为对应 Harness 的 Job Payload。
3. 状态回调映射为标准 `TaskProgress` 流式推送。
4. Web 前端完全无需修改任何调用逻辑。
