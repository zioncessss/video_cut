from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class HarnessCorrectionRequest(BaseModel):
    raw_subtitles: List[Dict[str, Any]]
    domain_context: str = "driving_school"
    custom_glossary: Optional[List[str]] = None

class SubtitleCorrectionItem(BaseModel):
    subtitle_id: str
    original_text: str
    corrected_text: str
    changes: List[Dict[str, str]] = []

class HarnessCorrectionResponse(BaseModel):
    updated_subtitles: List[Dict[str, Any]]
    corrections_summary: List[SubtitleCorrectionItem] = []
    harness_engine_used: str
    latency_ms: float = 0.0

    def __len__(self):
        return len(self.updated_subtitles)

    def __iter__(self):
        return iter(self.updated_subtitles)

    def __getitem__(self, index):
        return self.updated_subtitles[index]

class HarnessInstructionRequest(BaseModel):
    current_project_state: Dict[str, Any]
    user_instruction: str
    available_materials: Optional[List[Dict[str, Any]]] = None

class HarnessPlanResponse(BaseModel):
    explanation: str
    updated_subtitles: Optional[List[Dict[str, Any]]] = None
    updated_brolls: Optional[List[Dict[str, Any]]] = None
    harness_engine_used: str
    latency_ms: float = 0.0

class BaseHarnessBridge(ABC):
    @abstractmethod
    async def is_available(self) -> bool:
        """检测当前环境中的 Harness 运行时是否就绪"""
        pass

    @abstractmethod
    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> HarnessCorrectionResponse:
        """利用 Harness / LLM 对原始 ASR 字幕进行上下文与驾校专有词纠偏，统一返回契约对象"""
        pass

    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        """可选能力：解析开放式自然语言微调指令。不支持该能力的引擎必须显式报错，严禁返回假装成功的预置响应"""
        raise RuntimeError(f"{self.__class__.__name__} 不支持开放式指令理解，请配置并切换到 codex / zcode 智能体")

    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        """可选能力：批量混剪方案创意规划（当前无消费方，默认不支持）"""
        raise RuntimeError(f"{self.__class__.__name__} 不支持批量混剪方案规划")
