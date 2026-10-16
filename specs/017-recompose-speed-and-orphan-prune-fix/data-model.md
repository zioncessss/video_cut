# Data Model: 粗剪切片与渲染缓存实体模型

## 1. 粗剪切片模型 (PruneSpan & KeptSpan)

- `PruneSpan`:
  - `start_time`: 裁剪起始点（秒）
  - `end_time`: 裁剪结束点（秒）
  - `duration`: 时长（秒）
  - `reason`: `head_idle` | `tail_idle` | `retake_discard` | `mid_silence` | `manual`
  - `source_subtitle_id`: 对应被剔除的字幕 ID
  - `target_subtitle_id`: 被替换/被优选的保留字幕 ID
  - `is_active`: 是否生效布尔态

- `KeptSpan`:
  - `start_time`: 物理视频保留起始点（秒）
  - `end_time`: 物理视频保留结束点（秒）
  - `duration`: 保留时长（秒）
  - `audio_fade`: 是否执行 15ms afade 消音爆淡入淡出（默认 True）

## 2. 幽灵碎片判定规则 (Ghost Clip Definition)

一个保留区间 $K = [start, end]$ 被定义为“幽灵碎片（Ghost Clip）”当且仅当满足以下全部条件：
1. 时长 $duration = end - start < 0.60s$；
2. 在所有保留有效字幕中，不存在任何字幕区间 $[s_{start}, s_{end}]$ 满足 $s_{end} > start$ 且 $s_{start} < end$；
3. 其前后至少有一侧为裁剪区间。
处理方式：将此类区间强制合并入前侧或后侧的裁剪区间中。

## 3. 渲染决策状态机 (Render Decision State)

- **Tier 1 (Zero-Encode)**: `body_fp` 命中 ➡️ 直接复用现有成片文件。
- **Tier 2 (Sub-Only Fast Burn)**: `clean_base_fp` 命中且 `need_burn` ➡️ 复用高清底包，通过 `burn_subtitles_and_overlay_fast` 单独压制字幕，1~2s 完成。
- **Tier 3 (Single-Pass Direct Render)**: `clean_base_fp` 未命中 ➡️ 一次性调用 `compose_jl_cut(ass_subtitle_path=..., strategy=...)` 单次全流程直出成片，消除两次重编码。
