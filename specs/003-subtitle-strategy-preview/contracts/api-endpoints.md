# API Contracts: 剪辑策略与字幕呈现接口 (003-subtitle-strategy-preview)

## 1. 更新工程剪辑策略

- **Endpoint**: `PUT /api/v1/projects/{project_id}/strategy`
- **Method**: `PUT`
- **Description**: 用户在工作台策略面板或通过 AI 副驾驶对话调整剪辑策略时调用，持久化更新工程策略。

### Request Body
```json
{
  "subtitle_theme": "viral_gold",
  "font_size": "medium",
  "enable_highlight": true,
  "highlight_color": "#FACC15",
  "highlight_scale": true,
  "custom_highlight_words": ["一次过", "不收费"],
  "enable_top_banner": true,
  "banner_main_title": "新手学车必看 · 科目二",
  "banner_sub_title": "标准化考场实拍",
  "banner_style": "capsule",
  "enable_watermark": true,
  "watermark_text": "@顺达驾校官方教学",
  "watermark_position": "top_right",
  "watermark_opacity": 0.4,
  "broll_pacing": "fast"
}
```

### Response
```json
{
  "code": 0,
  "message": "剪辑策略已更新",
  "data": {
    "id": "proj-123",
    "strategy": { ... }
  }
}
```

---

## 2. 导出压制烧录（带策略滤镜）

- **Endpoint**: `POST /api/v1/projects/{project_id}/render`
- **Method**: `POST`
- **Description**: 将选定的字幕主题、高亮颜色、顶部 Title、品牌水印烧录进最终 MP4。

### Response
```json
{
  "id": "proj-123",
  "status": "completed",
  "output_video_path": "storage/outputs/output_proj-123_9_16.mp4"
}
```