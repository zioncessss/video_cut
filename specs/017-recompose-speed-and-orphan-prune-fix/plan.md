# Implementation Plan: 重新合成性能提速与粗剪幽灵碎片跳剪根治

**Branch**: `017-recompose-speed-and-orphan-prune-fix` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/017-recompose-speed-and-orphan-prune-fix/spec.md`

## Summary

1. 根治裁剪废动作残留与动作跳剪：
   - 粗剪引擎升级：`head_idle` 严格锚定全片首个真正保留的有效字幕；
   - 连续删除片段实现间隙闭包桥接，消除无声停顿碎片；
   - 增加幽灵片段扫描守卫（Ghost Clip Scrubber），吸收时长 `< 0.60s` 且无有效字幕的孤岛；
   - 提升区间吸附阈值至 `0.65s`。
2. 突破重新合成速度瓶颈：
   - 当底包未命中时，消除“先压底包、再压字幕”的二次全量重编码，直接单次 FFmpeg 完成切片、空镜、调色、字幕与横幅压制直出成片；
   - 优化画面缩放算法为 `bicubic+accurate_rnd`，消除 CPU 逐像素瓶颈，释放 GPU 硬件编码吞吐；
   - 纯字幕微调继续享受 1~2 秒极速烧录通道。

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.0+  
**Primary Dependencies**: FastAPI, FFmpeg, PIL (Pillow), React, TailwindCSS  
**Storage**: SQLite (`storage/videocut.db`) 权威存储，WAL 模式  
**Testing**: pytest  
**Target Platform**: Windows 10/11 (AMD AMF / NVIDIA NVENC / Intel QSV / CPU fallback)  
**Project Type**: Desktop Electron + Python Native Engine Backend  
**Performance Goals**:
- 重新合成全量直出耗时缩短 50%+（从 35~50s 降至 15s 以内）；
- 幽灵孤岛碎片发生率降为 0%；
- 314+ 全量单测 100% 通过。

## Constitution Check

- [x] **反假运行与防 Mock 铁律**: 严格调用真实 FFmpeg 与真实粗剪引擎，严禁对真实素材进行短路假合成。
- [x] **数据唯一事实源**: 保持 SQLite 唯一权威性，`prune_spans` 与 `compact_subtitles` 计算即持久化。
- [x] **高亮词与视觉策略零丢失**: 确保单次全流程直出通道与极速烧录通道 100% 消费并呈现 ASS 变色高亮与横幅。

## Project Structure

```text
specs/017-recompose-speed-and-orphan-prune-fix/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code Touches

- `backend/app/native_engine/prune_engine.py`:
  - `analyze_and_prune`: 修正 `head_idle` 判定，跳过 `sub.is_pruned == True` 的字幕；桥接连续剔除字幕的间隙。
  - `_merge_and_sort_spans`: 阈值由 0.35s 提升至 0.65s。
  - `compute_kept_spans`: 注入幽灵保留碎片（Ghost Clip）清洗逻辑。
- `backend/app/api/editor.py`:
  - `render_project`: 底包未命中时采用单次全流程直出通道（Single-Pass Direct Render），跳过冗余的二次重编码。
  - `_sync_prune_spans`: 联动清洗旧存量幽灵切片。
- `backend/app/native_engine/ffmpeg_filter.py`:
  - 缩放算法优化为高吞吐 `bicubic+accurate_rnd`。
- `tests/test_auto_prune_engine.py` & `tests/test_render_fast_path.py`:
  - 补充单次直出与幽灵碎片消除测试用例。
