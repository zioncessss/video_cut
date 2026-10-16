# Interface Contracts: 自主分镜切入裁剪与字幕重叠定位原口播视频误读裁剪 (Storyboard Trim & Subtitle Retake Pruning)

**Feature Branch**: `016-storyboard-trim-sub-retake-prune`
**Date**: 2026-10-14

## API Contracts

### 1. 智能口误识别与分析 (Detect Retakes)
- **Endpoint**: `POST /api/projects/{project_id}/detect-retakes`
- **Description**: 分析项目中当前字幕与音频，识别读错重读口误区间。
- **Response**:
```json
{
  "code": 200,
  "data": {
    "detected_retakes": [
      {
        "id": "retake_001",
        "start_time": 2.45,
        "end_time": 3.80,
        "retake_text": "我们顺达...",
        "replacement_text": "我们顺达驾校自建五万平训练场",
        "confidence": 0.96,
        "is_active": false
      }
    ],
    "count": 1
  }
}
```

---

### 2. 更新工程字幕与物理裁剪标记 (Update Subtitles & Pruning)
- **Endpoint**: `PUT /api/projects/{project_id}/subtitles`
- **Request Body**:
```json
{
  "subtitles": [
    {
      "id": "sub_1",
      "start_time": 0.0,
      "end_time": 2.45,
      "text": "大家好，学车看这里",
      "highlight_words": ["学车"],
      "is_pruned": false
    },
    {
      "id": "sub_2_pruned",
      "start_time": 2.45,
      "end_time": 3.80,
      "text": "我们顺达...",
      "highlight_words": [],
      "is_pruned": true,
      "prune_span_id": "retake_001"
    },
    {
      "id": "sub_3",
      "start_time": 3.80,
      "end_time": 6.50,
      "text": "我们顺达驾校自建五万平训练场",
      "highlight_words": ["顺达驾校", "训练场"],
      "is_pruned": false
    }
  ],
  "prune_spans": [
    {
      "id": "retake_001",
      "start_time": 2.45,
      "end_time": 3.80,
      "reason": "retake",
      "is_active": true
    }
  ]
}
```
- **Response**:
```json
{
  "code": 200,
  "data": {
    "success": true,
    "effective_duration": 5.15,
    "updated_at": "2026-10-14T10:50:00Z"
  }
}
```

---

### 3. 分镜切入与素材截取配置 (Save B-roll Replacements)
- **Endpoint**: `PUT /api/projects/{project_id}/brolls`
- **Request Body**:
```json
{
  "brolls": [
    {
      "id": "broll_01",
      "material_id": "mat_venue_02",
      "material_path": "storage/materials/venue/training_ground.mp4",
      "target_start_time": 2.5,
      "target_end_time": 5.6,
      "source_start_time": 1.8,
      "audio_mode": "mute",
      "scale_mode": "cover"
    }
  ]
}
```
- **Response**:
```json
{
  "code": 200,
  "data": {
    "success": true,
    "broll_count": 1
  }
}
```

---

### 4. 视频最终导出压制契约 (Render Export)
- **Endpoint**: `POST /api/projects/{project_id}/render`
- **Request Body**:
```json
{
  "export_resolution": "1080p",
  "playback_rate": 1.0,
  "enable_highlight": true
}
```
- **Processing Rule**:
  1. 收集所有 `is_active=true` 的 `prune_spans`，计算 `kept_spans`；
  2. 使用 `[0:v]trim` 与 `[0:a]atrim` + `concat` 真正物理剔除误读音画，接缝处注入 15ms `afade`；
  3. 分镜素材提取 `source_start_time` 截取片段并按 `target_start_time` 覆盖主视频画面，分镜音轨剥离；
  4. 字幕时间轴平移对齐并渲染 ASS，绝对保留高亮词。
