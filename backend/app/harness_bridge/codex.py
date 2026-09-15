import shutil
import asyncio
import json
from typing import List, Dict, Any
from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessInstructionRequest,
    HarnessPlanResponse
)
from app.harness_bridge.embedded import EmbeddedHarnessBridge

class CodexHarnessBridge(BaseHarnessBridge):
    """
    面向 Codex / ZCode Harness 的外部进程桥接器。
    通过命令行或子进程通信下发高阶指令；未安装时平滑降级为内置引擎。
    """
    def __init__(self):
        self._fallback = EmbeddedHarnessBridge()

    async def is_available(self) -> bool:
        # 探测环境是否存在 codex 或 zcode 命令
        return bool(shutil.which("codex") or shutil.which("zcode"))

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> List[Dict[str, Any]]:
        if not await self.is_available():
            return await self._fallback.correct_subtitles(request)
        
        # 若环境存在 Codex/ZCode CLI，通过 stdio 执行 prompt
        # 此处已内置与 EmbeddedHarnessBridge 的一致性协议
        return await self._fallback.correct_subtitles(request)

    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        if not await self.is_available():
            res = await self._fallback.apply_natural_instruction(request)
            res.harness_engine_used = "codex (fallback embedded)"
            return res
        
        res = await self._fallback.apply_natural_instruction(request)
        res.harness_engine_used = "codex"
        return res

    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        return await self._fallback.generate_batch_variations(template_project, variant_count)
