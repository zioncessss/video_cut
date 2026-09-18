# API & Component Contracts: 字幕实时保存与成片预览所见即所得同步

**Feature**: `007-subtitle-sync-preview`  
**Date**: 2026-09-19  

## 1. Web API Contracts

### 1.1 更新工程字幕列表 (PUT /api/projects/{project_id}/subtitles)

- **Method**: `PUT`
- **Path**: `/api/projects/{project_id}/subtitles`
- **Request Body**:
  ```json
  {
    "subtitles": [
      {
        "id": "sub_1",
        "start_time": 1.2,
        "end_time": 3.8,
        "raw_text": "让我讲一讲",
        "corrected_text": "让我讲一讲",
        "matched_category": null,
        "matched_keywords": [],
        "highlight_words": [
          { "word": "讲一讲", "source": "manual", "color": "#FACC15" }
        ],
        "is_manual_edited": true
      }
    ],
    "broll_replacements": null
  }
  ```
- **Response**: `200 OK` (返回完整更新后的 `CutProject` JSON 对象)
- **Error Response**:
  - `404 Not Found`: `{ "detail": "工程不存在" }`
  - `422 Unprocessable Entity`: `{ "detail": [ ...validation errors... ] }`

---

### 1.2 复合渲染并生成导出成片 (POST /api/projects/{project_id}/render)

- **Method**: `POST`
- **Path**: `/api/projects/{project_id}/render`
- **Prerequisite**: 必须在持久化保存完最新字幕与策略后调用。
- **Response**: `200 OK`
  ```json
  {
    "id": "proj_123",
    "status": "completed",
    "output_video_path": "storage/tasks/clip_20260919/output_proj_123_9_16_1726712345.mp4",
    "output_filename": "output_proj_123_9_16_1726712345.mp4",
    "output_file_size_mb": 14.52,
    "output_absolute_path": "D:\\project\\video_cut\\storage\\tasks\\clip_20260919\\output_proj_123_9_16_1726712345.mp4"
  }
  ```

---

## 2. Frontend Component Interface Contracts

### 2.1 SubtitleList Props

```typescript
export interface SubtitleListProps {
  subtitles: SubtitleItem[];
  currentTime: number;
  saveStatus?: 'idle' | 'dirty' | 'saving' | 'saved' | 'error';
  lastSavedAt?: number | null;
  onSelectTime: (time: number) => void;
  onTextChange: (index: number, newText: string) => void;
  onTextBlur?: (index: number) => void;
  onHighlightWordsChange: (index: number, words: HighlightWord[]) => void;
  onRetrySave?: () => void;
}
```

### 2.2 VideoPlayer Props & Active Viewport

```typescript
export interface VideoPlayerProps {
  videoUrl: string;
  brolls?: any[];
  materialsMap?: Record<string, any>;
  subtitles: SubtitleItem[];
  currentTime: number;
  onTimeUpdate: (time: number) => void;
  aspectRatio?: '9:16' | '16:9';
  onAspectRatioChange?: (aspect: '9:16' | '16:9') => void;
  strategy?: EditingStrategy;
  onStrategyChange?: (newStrategy: EditingStrategy) => void;
  onStrategyCommit?: (committedStrategy: EditingStrategy) => void;
  isRendered?: boolean;
}
```
