# 混合驱动 Harness 适配器接口协议 (Hybrid Harness Adapter Contract)

**Version**: 2.0.0  
**Pattern**: Dual-Engine (Native Hardcoded + Harness Wrapper)  

---

## 1. 架构定位

- **Native Engine（本地硬编码内核）**：负责固定高频任务——素材存取、视频探测、基础 ASR、确定性 FFmpeg 滤镜压制、硬件资源探测。
- **Harness Wrapper（智能体套壳层）**：负责高阶灵活任务——自然语言语义纠偏、对话式微调指令理解、多样化混剪剧本生成、外部 Codex/ZCode 进程调用。

---

## 2. 核心接口定义 (Core Interfaces)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# === 高阶操作：Harness 任务载荷 ===
class HarnessCorrectionRequest(BaseModel):
    """请求 Harness 执行上下文专有词纠错"""
    raw_subtitles: List[Dict[str, Any]]
    domain_context: str = "driving_school"  # 驾校垂直领域
    custom_glossary: Optional[List[str]] = None

class HarnessInstructionRequest(BaseModel):
    """用户在底部输入的自然语言微调指令"""
    current_project_state: Dict[str, Any]
    user_instruction: str  # 例如："把第3句空镜换成另一个场地素材，把语速较慢的片段适当压缩"

class HarnessPlanResponse(BaseModel):
    """Harness 返回的高阶修改建议或更新后的剪辑状态"""
    explanation: str
    updated_subtitles: Optional[List[Dict[str, Any]]] = None
    updated_brolls: Optional[List[Dict[str, Any]]] = None
    harness_engine_used: str  # "codex" | "zcode" | "embedded"

# === 抽象基类：Harness 适配器 ===
class BaseHarnessBridge(ABC):
    @abstractmethod
    async def is_available(self) -> bool:
        """检测当前环境中的 Codex / ZCode Harness 是否就绪"""
        pass

    @abstractmethod
    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> List[Dict[str, Any]]:
        """利用 Harness / LLM 对原始 ASR 字幕进行上下文与驾校专有词纠偏"""
        pass

    @abstractmethod
    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        """解析用户自然语言微调意图，并动态调整剪辑工程配置"""
        pass

    @abstractmethod
    async def generate_batch_variations(self, template_project: Dict[str, Any], variant_count: int) -> List[Dict[str, Any]]:
        """利用 Harness 创意规划能力，批量生成不同镜头编排维度的混剪方案"""
        pass
```

---

## 3. 固化层与套壳层的交互流程 (Workflow)

1. **用户上传与 ASR**：由 Native Engine 执行，直接提取出 `raw_subtitles`。
2. **术语纠错与智能打标**：Native Engine 将数据封装给 `HarnessBridge.correct_subtitles()`，Harness 调取智能体完成语义纠错与关键词标记。
3. **前端渲染展示**：用户看到左侧视频 + 右侧带标签的字幕卡片。
4. **底部自然语言微调**：用户输入指令 -> Native Engine 转发给 `HarnessBridge.apply_natural_instruction()` -> Harness 返回调整方案并应用。
5. **最终合成渲染**：点击“生成” -> Native Engine 组装结构化 FFmpeg 指令直接进行多轨高精度硬件加速压制。
