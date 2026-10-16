# Data Model: 自主分镜切入裁剪与字幕重叠定位原口播视频误读裁剪 (Storyboard Trim & Subtitle Retake Pruning)

**Feature Branch**: `016-storyboard-trim-sub-retake-prune`
**Date**: 2026-10-14

## Entity Definitions & Schemas

### 1. BrollReplacement (分镜替换实体)
扩展既有分镜实体，增加素材截取 In 点 (`source_start_time`)。

```typescript
interface BrollReplacement {
  id: string;                     // 分镜唯一标识 (UUID)
  material_id: string;            // 关联素材库 ID
  material_path: string;          // 磁盘真实素材文件路径
  target_start_time: number;      // 主视频切入开始时间 (秒, >= 0)
  target_end_time: number;        // 主视频切入结束时间 (秒, > target_start_time)
  source_start_time: number;      // 素材截取起始点 In 点 (秒, 默认为 0.0)
  source_duration?: number;       // 截取时长，默认自动等于 target_end_time - target_start_time
  audio_mode: 'mute';             // 固定为静音模式 (Clarify 决议)
  scale_mode: 'cover' | 'contain';// 画面缩放模式
}
```

**Validation Rules**:
- `target_end_time > target_start_time`
- `source_start_time >= 0`
- `source_start_time + (target_end_time - target_start_time) <= material.duration`（防黑屏越界截断校验）

---

### 2. PruneSpan / VoiceRetakeSpan (裁剪与重读区间实体)

```typescript
interface PruneSpan {
  id: string;                     // 裁剪区间 ID
  start_time: number;             // 原视频开始时间 (秒)
  end_time: number;               // 原视频结束时间 (秒)
  reason: 'retake' | 'silence' | 'manual'; // 裁剪原因：重读、静音、手动
  detected_text?: string;         // 读错的文本 (若为口误)
  correct_text?: string;          // 读对的文本 (若为口误)
  confidence?: number;            // 算法判定置信度 (0.0 ~ 1.0)
  is_active: boolean;             // 当前是否已生效裁剪 (true=已剔除物理跳播, false=已恢复)
}
```

**State Transitions**:
- `DETECTED` (高置信识别为口误重读) $\xrightarrow{\text{用户或自动点击剔除}}$ `PRUNED` (`is_active = true`，原视频音画物理排除，字幕卡片折叠为浅灰微条)
- `PRUNED` $\xrightarrow{\text{用户点击恢复}}$ `RESTORED` (`is_active = false`，音画及字幕无损恢复原位，时间轴重算)

---

### 3. SubtitleItem (字幕条目实体)

```typescript
interface SubtitleItem {
  id: string;                     // 字幕 ID
  start_time: number;             // 显示起始时间 (已扣除前序已裁切时长的有效时间轴)
  end_time: number;               // 显示结束时间
  raw_start_time?: number;        // 原始口播视频绝对时间戳
  raw_end_time?: number;          // 原始口播视频绝对时间戳
  text: string;                   // 字幕正文
  highlight_words: string[];      // 重点关键词高亮 (零丢失策略保障)
  is_pruned: boolean;             // 是否被标记剔除
  prune_span_id?: string;         // 关联的物理裁剪区间 ID
  is_manual_added?: boolean;      // 是否为手动插入字幕
  broll_id?: string;              // 挂载的分镜 ID (可选)
}
```

---

### 4. ProjectEditState (剪辑工程全状态聚合)

```typescript
interface ProjectEditState {
  project_id: string;
  video_path: string;
  original_duration: number;
  effective_duration: number;     // 扣除所有 active prune_spans 后的实际成片时长
  playback_rate: number;          // 播放倍速 (1.0x, 1.1x, 1.25x 等)
  subtitles: SubtitleItem[];
  brolls: BrollReplacement[];
  prune_spans: PruneSpan[];
}
```
