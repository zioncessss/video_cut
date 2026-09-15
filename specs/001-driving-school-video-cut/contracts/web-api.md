# Web API 交互契约 (Web API Contract)

**Version**: 1.0.0  
**Transport**: HTTP REST + WebSocket / SSE  
**Base URL**: `http://localhost:18888/api/v1`  

---

## 1. 素材管理接口 (Materials)

### 1.1 上传素材
- **Endpoint**: `POST /materials/upload`
- **Content-Type**: `multipart/form-data`
- **Request Parameters**:
  - `category`: `talking_head` | `venue` | `medical` | `lesson`
  - `file`: 视频二进制流
- **Response**:
```json
{
  "code": 0,
  "data": {
    "id": "mat-123e4567-e89b-12d3-a456-426614174000",
    "category": "venue",
    "filename": "site_aerial_view.mp4",
    "filepath": "storage/materials/venue/site_aerial_view.mp4",
    "duration": 12.45,
    "width": 1080,
    "height": 1920,
    "fps": 30.0
  }
}
```

### 1.2 列表素材
- **Endpoint**: `GET /materials?category={category}`
- **Response**: 返回指定分类或全部分类的素材元数据数组。

---

## 2. 剪辑工作台接口 (Editor & Cut Workflow)

### 2.1 口播解析与初始剪辑生成
- **Endpoint**: `POST /projects/analyze-and-cut`
- **Request**:
```json
{
  "talking_head_id": "mat-123",
  "aspect_ratio": "9:16",
  "auto_broll": true
}
```
- **Response**:
```json
{
  "code": 0,
  "data": {
    "project_id": "proj-987",
    "title": "科目二倒库技巧与场地介绍",
    "duration": 48.2,
    "subtitles": [
      {
        "id": "sub-1",
        "start_time": 0.0,
        "end_time": 3.8,
        "text": "同学们好，今天带大家看看我们五万平的标准化训练场。",
        "matched_category": "venue",
        "matched_keywords": ["标准化训练场", "五万平"],
        "broll_material_id": "mat-venue-01"
      }
    ]
  }
}
```

### 2.2 更新字幕与空镜替换规则
- **Endpoint**: `PUT /projects/{project_id}/subtitles`
- **Request**: 包含更新后的字幕文本、时间戳及关联的空镜素材 ID。

### 2.3 触发视频渲染
- **Endpoint**: `POST /projects/{project_id}/render`
- **Response**: 返回任务 ID，并通过 WebSocket 推送渲染进度。

---

## 3. 硬件资源与批量生产 (Hardware & Batch)

### 3.1 查询硬件资源与建议并发
- **Endpoint**: `GET /system/resources`
- **Response**:
```json
{
  "cpu_cores": 16,
  "cpu_usage_percent": 18.5,
  "memory_total_gb": 32.0,
  "memory_available_gb": 22.4,
  "gpu_acceleration": "nvenc",
  "recommended_concurrency": 4
}
```

### 3.2 提交批量生产作业
- **Endpoint**: `POST /batch/jobs`
- **Request**:
```json
{
  "talking_head_ids": ["mat-1", "mat-2"],
  "generate_variants_per_video": 3,
  "concurrency_limit": 4
}
```

### 3.3 实时进度推送 (WebSocket)
- **Endpoint**: `WS /ws/progress`
- **Event Payload**:
```json
{
  "event": "task_progress",
  "job_id": "batch-001",
  "task_id": "task-01",
  "progress": 65.5,
  "stage": "ffmpeg_render",
  "current_fps": 74.2
}
```
