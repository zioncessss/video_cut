---
description: "Task list for smart pruning of silence, retakes, and natural breath gap preservation"
---

# Tasks: 智能剔除口播视频头尾动作与口误重说 (009-prune-retakes-silence)

**Input**: Design documents from `/specs/009-prune-retakes-silence/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)

---

## Phase 1: Setup & Foundational (基础设施与数据存储)

**Purpose**: 准备数据模型、SQLite 字段迁移与基础设施定义

- [x] T001 [P] 扩展 Pydantic 数据模型：在 `backend/app/models/entities.py` 中增加 `PruneSpan`、`PruneStrategyConfig` 与 `KeptSpan` 实体
- [x] T002 [P] 扩展 SQLite 数据库字段：在 `backend/app/db/schema.sql` 中为 `projects` 增加 `prune_spans_json`，为 `subtitles` 增加 `is_pruned` 与 `prune_reason`
- [x] T003 更新数据仓库层：在 `backend/app/db/repository.py` 中增加对 `prune_spans_json`、`is_pruned` 的持久化读写与迁移兼容逻辑
- [x] T004 创建核心算法模块骨架：在 `backend/app/native_engine/prune_engine.py` 中定义 `AutoPruneEngine` 基础类与计算接口

**Checkpoint**: 基础模型与数据访问层就绪，可通过纯代码实例化调用。

---

## Phase 2: User Story 1 - 手机口播录制头尾动作与静音自动剔除 (Priority: P1) 🎯 MVP

**Goal**: 自动分析 ASR 语音时间轴，精确定位首句人声前（保留 0.20s 气口）与尾句收音后（保留 0.25s 气口）的多余区间并生成 `head_idle` 与 `tail_idle` 剔除区间。

- [x] T005 [P] [US1] 编写头尾废动作裁剪单元测试：在 `tests/test_auto_prune_engine.py` 中编写头部/尾部动作裁剪与安全气口保留的测试用例
- [x] T006 [US1] 实现头尾裁剪算法：在 `backend/app/native_engine/prune_engine.py` 中实现首句人声前与末句人声后的 `PruneSpan` 计算，严格保留 `head_padding_seconds` (0.20s) 与 `tail_padding_seconds` (0.25s)
- [x] T007 [US1] 集成到自动化剪辑流程：在 `backend/app/api/batch.py` 中于 ASR 识别后调用 `AutoPruneEngine` 执行头尾动作剔除，并将生成的切片存入工程元数据

**Checkpoint**: 运行 `pytest tests/test_auto_prune_engine.py -k test_head_tail` 绿灯，视频头尾废动作能被准确标记且无吞字。

---

## Phase 3: User Story 2 - 口误重说与卡壳智能识别“留后弃前”与长停顿压缩 (Priority: P1)

**Goal**: 基于滑动窗口、停顿特征（0.4s~1.5s）与文本重合度，自动识别口误重说并遵循“舍弃前驱、保留后效”；中段无声长停顿（>1.2s）自动压缩并保留 0.30s~0.35s 自然换气气口。

- [x] T008 [P] [US2] 编写口误重说与长停顿压缩测试：在 `tests/test_auto_prune_engine.py` 中增加针对《湖州驾校》与《经常有评论》典型口误用例及中段长停顿压缩的测试断言
- [x] T009 [US2] 实现口误重说检测算法：在 `backend/app/native_engine/prune_engine.py` 中基于 `difflib.SequenceMatcher` 与停顿特征识别重说，支持多次连续重说链追溯，将前置未完成片段标记为 `retake_discard`
- [x] T010 [US2] 实现中段单纯长停顿气口压缩：在 `backend/app/native_engine/prune_engine.py` 中对无重说的 `gap > 1.2s` 静音段生成 `mid_silence` 剔除区间，两端各保留 0.15s 自然呼吸停顿
- [x] T011 [US2] 计算有效保留区间序列：在 `backend/app/native_engine/prune_engine.py` 中实现 `compute_kept_spans`，将所有活跃的 `prune_spans` 反向投影计算为连续递增的 `kept_spans`

**Checkpoint**: 运行 `pytest tests/test_auto_prune_engine.py` 全部绿灯，口误重说与卡壳停顿精准识别。

---

## Phase 4: User Story 3 - 粗剪结果可视化审阅与可逆微调 (Priority: P2)

**Goal**: 在剪辑工作台中通过客户端虚拟跳播（0 延迟跳过剔除区间）直观预览成片，字幕列表与时间轴清晰标注剔除状态，提供一键恢复与微调 API。

- [x] T012 [P] [US3] 实现工作台剔除状态切换 API：在 `backend/app/api/editor.py` 中增加 `/api/editor/projects/{project_id}/subtitles/{subtitle_id}/toggle-prune` 接口
- [x] T013 [P] [US3] 更新前端 API 服务层：在 `frontend/src/services/api.ts` 中补充 `toggleSubtitlePrune` 与 `PruneSpan` 相关接口定义
- [x] T014 [US3] 实现播放器虚拟跳播与剔除条带渲染：在 `frontend/src/components/VideoPlayer.tsx` 中监听 `currentTime` 实现自动跳过 `prune_spans`，并在进度条底层渲染剔除区间阴影
- [x] T015 [US3] 优化字幕列表剔除交互：在 `frontend/src/components/SubtitleList.tsx` 中对 `is_pruned` 的字幕项增加灰色划线视觉与【恢复/剔除】切换操作按钮

**Checkpoint**: 打开前端编辑台，已剔除的头尾与口误片段能自动跳过播放，点击“恢复”能即时撤销并恢复播放。

---

## Phase 5: User Story 4 - 批量处理集成与 FFmpeg 导出声画对齐防爆音 (Priority: P3)

**Goal**: 导出视频时利用 `kept_spans` 驱动 FFmpeg 复合切片滤镜，结合微秒级音频淡入淡出（afade）消除硬切爆音，空镜与 ASS 字幕自动重新对齐时间轴。

- [x] T016 [US4] 改造 FFmpeg 多轨合成管线：在 `backend/app/native_engine/ffmpeg_filter.py` 中基于 `kept_spans` 重构音画提取与拼接，并在音频片段首尾添加 15ms `afade` 防爆音滤镜
- [x] T017 [US4] 保持空镜与字幕在紧凑时间轴对齐：在 `backend/app/native_engine/scene_decision.py` 与 `subtitle_styler.py` 中确保空镜切片规避已剔除区间，ASS 字幕时间戳映射至裁剪后的紧凑时间轴
- [x] T018 [P] [US4] 编写导出与防爆音回归测试：在 `tests/test_prune_video_export.py` 中测试生成包含头尾剔除与口误重说的视频导出指令与实际渲染效果

---

## Phase 6: Polish & Verification (全量回归与真实视频验证)

- [x] T019 针对项目库 5 部真实手机口播视频执行粗剪全流程验证测试，确保识别率与气口舒适度达标
- [x] T020 检查前后端代码风格与无用依赖，确保遵循极简原则（Ponytail & Global Rules）
