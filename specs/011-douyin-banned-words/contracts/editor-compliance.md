# API Contract: 违禁词检测与合规导出接口

## 1. 违禁词预检接口 (Banned Words Check)

- **HTTP 方法**: `GET`
- **路径**: `/api/editor/projects/{project_id}/banned_words_check`
- **说明**: 检索当前工程中所有有效字幕片段，返回违禁词命中情况与替换预览，用于前端导出弹窗展示。

### 请求参数
- 路径参数:
  - `project_id` (string, required): 剪辑工程 ID

### 响应体 (200 OK)
```json
{
  "project_id": "e4257e38-f170-45c4-84a7-ab2d2abd1547",
  "has_banned_words": true,
  "total_matches": 3,
  "matches": [
    {
      "subtitle_index": 1,
      "original_word": "驾照",
      "replacement_word": "贺照",
      "original_line": "在杭州考一个驾照要多少钱",
      "sanitized_line": "在杭州考一个贺照要多少銭"
    },
    {
      "subtitle_index": 1,
      "original_word": "钱",
      "replacement_word": "銭",
      "original_line": "在杭州考一个驾照要多少钱",
      "sanitized_line": "在杭州考一个贺照要多少銭"
    },
    {
      "subtitle_index": 6,
      "original_word": "体检",
      "replacement_word": "体脸",
      "original_line": "体检费这些加起来大概是一百",
      "sanitized_line": "体脸弗这些加起来大概是一百"
    }
  ]
}
```

---

## 2. 导出/渲染成片接口 (Render Project)

- **HTTP 方法**: `POST`
- **路径**: `/api/editor/projects/{project_id}/render`
- **说明**: 发起 FFmpeg 视频合成，新增 `filter_banned_words` 控制参数。

### 请求参数
- 路径参数:
  - `project_id` (string, required): 剪辑工程 ID
- 查询参数:
  - `video_speed` (float, optional): 导出倍速 (默认 1.0)
  - `filter_banned_words` (bool, optional, 默认 True): 是否在烧录字幕前执行违禁词清洗

### 响应体 (200 OK)
返回标准的 `CutProject` 结构体，包含 `output_video_path`、`output_filename`、`output_file_size_mb` 等。

---

## 3. 词库管理接口 (可选扩展)

- **HTTP 方法**: `GET` / `PUT`
- **路径**: `/api/settings/banned_words`
- **说明**: 获取当前系统加载的违禁词映射字典或更新字典。