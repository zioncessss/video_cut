# Contract: 智能粗剪引擎接口规范 (009-prune-retakes-silence)

## 1. 核心 Python 服务契约 (`AutoPruneEngine`)

服务定位：`backend/app/native_engine/prune_engine.py`

```python
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel

class PruneSpan(BaseModel):
    id: str
    start_time: float
    end_time: float
    reason: str  # head_idle | tail_idle | retake_discard | mid_silence | manual
    source_subtitle_id: str | None = None
    target_subtitle_id: str | None = None
    duration: float
    is_active: bool = True

class PruneAnalysisResult(BaseModel):
    prune_spans: List[PruneSpan]
    pruned_subtitle_ids: List[str]
    total_pruned_seconds: float
    natural_breath_gaps_preserved: int  # 统计保留的自然生理停顿数
    summary: Dict[str, Any]

class AutoPruneEngine:
    def analyze_and_prune(
        self,
        subtitles: List[Dict[str, Any]],
        video_duration: float,
        config: Dict[str, Any] | None = None
    ) -> PruneAnalysisResult:
        """
        输入原始字幕条目序列及视频时长，输出剔除区间与需剔除的字幕 ID 清单。
        严格确保首尾与断句处保留自然呼吸气口。
        """
        ...

    def compute_kept_spans(
        self,
        video_duration: float,
        prune_spans: List[PruneSpan]
    ) -> List[Tuple[float, float]]:
        """
        根据原始总时长和有效生效的剔除区间，计算最终用于播放和 FFmpeg 压制的保留时间块序列。
        """
        ...
```

---

## 2. HTTP / REST API 契约

### 2.1 切换字幕剔除状态 (Toggle Subtitle Prune)
- **Method**: `POST`
- **Path**: `/api/editor/projects/{project_id}/subtitles/{subtitle_id}/toggle-prune`
- **Request Body**:
  ```json
  {
    "is_pruned": false
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "subtitle_id": "...",
    "is_pruned": false,
    "prune_spans": [ ... ],
    "total_effective_duration": 28.4
  }
  ```

---

### 2.2 更新粗剪策略与重新分析 (Re-analyze Prune)
- **Method**: `POST`
- **Path**: `/api/editor/projects/{project_id}/prune-config`
- **Request Body**:
  ```json
  {
    "enable_head_prune": true,
    "enable_tail_prune": true,
    "enable_retake_prune": true,
    "enable_mid_silence_prune": true,
    "head_padding_seconds": 0.20,
    "tail_padding_seconds": 0.25,
    "mid_silence_threshold": 1.20,
    "mid_silence_breath_gap": 0.30
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "total_pruned_seconds": 6.85,
    "prune_spans": [ ... ]
  }
  ```

---

## 3. 前端播放器通信与跳播协议

前端 `VideoPlayer.tsx` 接收 `prune_spans: PruneSpan[]`：
- 在 `tick` 帧渲染监听：
  ```ts
  const activeSpan = pruneSpans.find(s => s.is_active && cur >= s.start_time && cur < s.end_time);
  if (activeSpan) {
    videoRef.current.currentTime = activeSpan.end_time + 0.01;
  }
  ```
- 时间轴（Scrubber）渲染：在进度条底层以背景条状显示各个剔除区间，悬浮提示剔除原因（如“已剔除：开机准备动作 (0.0s - 3.5s)”）。
