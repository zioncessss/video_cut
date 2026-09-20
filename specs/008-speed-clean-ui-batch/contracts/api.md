# API Contract: 视频编辑倍速与批量混剪扩展 (008)

## 1. PUT /api/v1/projects/{project_id}/strategy
**请求体**:
```json
{
  "subtitle_theme": "glow_gold",
  "font_size": "medium",
  "show_subtitles": true,
  "video_speed": 1.1,
  ...
}
```
**响应**: 返回更新后的 `CutProject` 对象。

## 2. POST /api/v1/batch/upload-and-cut
**请求 (multipart/form-data)**:
- `files`: 多视频文件
- `aspect_ratio`: "9:16" | "16:9"
- `concurrency`: 可选整数
- `video_speed`: 浮点数 (如 1.1)

**响应 (200 OK)**:
```json
{
  "code": 0,
  "data": {
    "job_id": "8f391b4e-...",
    "queued": 5,
    "concurrency": 4,
    "video_speed": 1.1
  }
}
```