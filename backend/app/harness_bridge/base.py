from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class HarnessCorrectionRequest(BaseModel):
    raw_subtitles: List[Dict[str, Any]]
    domain_context: str = "driving_school"
    custom_glossary: Optional[List[str]] = None

class HarnessInstructionRequest(BaseModel):
    current_project_state: Dict[str, Any]
    user_instruction: str

class HarnessPlanResponse(BaseModel):
    explanation: str
    updated_subtitles: Optional[List[Dict[str, Any]]] = None
    updated_brolls: Optional[List[Dict[str, Any]]] = None
    harness_engine_used: str

class BaseHarnessBridge(ABC):
    @abstractmethod
    async def is_available(self) -> bool:
        """检测当前环境中的 Harness 运行时是否就绪"""
        pass

    @abstractmethod
    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> List[Dict[str, Any]]:
        """利用 Harness / LLM 对原始 ASR 字幕进行上下文与驾校专有词纠偏"""
        pass

    @abstractmethod
    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        """解析用户在底部输入的自然语言微调意图，动态调整剪辑工程配置"""
        pass

    @abstractmethod
    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        """利用 Harness 创意规划能力，批量生成不同镜头编排维度的混剪方案"""
        pass
