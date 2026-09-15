# Phase 1 Data Model: 数据模型与实体定义

## 1. 系统设置实体 (System Settings)

```python
class SettingsModel(BaseModel):
    active_harness: str = "codex"  # "codex" | "zcode" | "embedded"
    llm_model: Optional[str] = None  # 可选 -m 覆盖参数，None 时继承 ~/.codex/config.toml
    updated_at: float = Field(default_factory=time.time)

class HarnessTestRequest(BaseModel):
    engine: str = "codex"
    model_override: Optional[str] = None

class HarnessTestResponse(BaseModel):
    success: bool
    engine: str
    active_model: str
    latency_ms: float
    message: str
    raw_error: Optional[str] = None
```

## 2. 智能纠错数据载荷 (Subtitle Correction)

```python
class SubtitleCorrectionItem(BaseModel):
    subtitle_id: str
    original_text: str
    corrected_text: str
    changes: List[Dict[str, str]] = Field(default_factory=list)
    # 示例: [{"from": "科尔", "to": "科目二", "reason": "驾校专有名词规范化"}]

class SubtitleCorrectionResult(BaseModel):
    updated_subtitles: List[Dict[str, Any]]
    corrections_summary: List[SubtitleCorrectionItem]
    harness_engine_used: str  # "codex" | "embedded (fallback)"
    latency_ms: float
```

## 3. 全能自然语言微调载荷 (Natural Language Instruction)

```python
class NaturalInstructionPayload(BaseModel):
    instruction: str
    current_subtitles: List[Dict[str, Any]]
    current_brolls: List[Dict[str, Any]]
    available_materials: Optional[List[Dict[str, Any]]] = None

class NaturalInstructionResponse(BaseModel):
    code: int = 0
    message: str
    explanation: str
    updated_subtitles: List[Dict[str, Any]]
    updated_brolls: List[Dict[str, Any]]
    harness_engine_used: str
    latency_ms: float
```