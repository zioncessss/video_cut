# Data Model: 视频编辑倍速、Taste UI 与批量混剪工作台 (008)

## 1. 实体扩展

### EditingStrategy (扩展)
新增字段 `video_speed`：
```python
class EditingStrategy(BaseModel):
    ...
    video_speed: float = 1.0  # 视频剪辑与压制倍速（推荐: 1.0, 1.1, 1.15, 1.2, 1.25；范围 0.75~2.0）
```

- **数据校验**:
  - `0.75 <= video_speed <= 2.0`
  - 默认值 `1.0`
  - 持久化：写入 SQLite `projects.strategy` JSON 列中，与已有工程无缝兼容。

### BatchSubmitRequest / upload_and_cut (扩展)
```python
class BatchSubmitRequest(BaseModel):
    material_ids: List[str]
    aspect_ratio: str = "9:16"
    concurrency: Optional[int] = None
    video_speed: float = 1.0  # 批量混剪应用的目标倍速
```

```python
@router.post("/upload-and-cut")
async def upload_and_cut(
    bg_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    aspect_ratio: str = Form("9:16"),
    concurrency: Optional[int] = Form(None),
    video_speed: float = Form(1.0)
): ...
```

---

## 2. 前端模型状态映射 (TypeScript)

### EditingStrategy
```typescript
export interface EditingStrategy {
  ...
  video_speed?: number; // 默认 1.0
}
```

### BatchCut 页面状态
```typescript
interface BatchCutState {
  viewMode: 'gallery' | 'queue';  // 双模态：成片画廊（默认）vs 任务队列
  batchAspectRatio: '9:16' | '16:9';
  batchSpeed: number;             // 1.0 | 1.1 | 1.2
  customConcurrency: number | '';
  selectedFiles: File[];
  isUploadOpen: boolean;
}
```