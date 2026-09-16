# Tasks: 口播视频字幕增强与多剪辑策略组合实验 (003-subtitle-strategy-preview)

Status: Completed | Priority: P1 | Spec: [spec.md](./spec.md) | Plan: [plan.md](./plan.md)

---

## Phase 1: 数据模型与后端基座扩展 (Backend Core)

- [x] Task 1.1: 在 `backend/app/models/entities.py` 中增加 `EditingStrategy` Pydantic 数据模型，并在 `CutProject` 中持有 `strategy`（提供爆款预设作为默认值）。
- [x] Task 1.2: 在 `backend/app/native_engine/asr_runner.py` 中实现 `split_into_readable_segments()` 算法，针对 > 12 字的长句按标点/声学停顿切分为短促口播字幕。
- [x] Task 1.3: 在 `backend/app/api/editor.py` 中实现 `PUT /api/v1/projects/{project_id}/strategy` API 端点，支持前端与 Harness 随时更新剪辑策略。
- [x] Task 1.4: 升级 `backend/app/native_engine/subtitle_styler.py` 与 `backend/app/native_engine/ffmpeg_filter.py`，支持 ASS 独立高亮变色以及顶部 Title / 水印复合滤镜压制。
- [x] Task 1.5: 编写单元测试 `tests/test_subtitle_strategy.py` 并验证后端逻辑全通。

---

## Phase 2: 前端策略工作台与播放器即时预览 (Frontend Studio)

- [x] Task 2.1: 创建 `frontend/src/components/StrategyStudio.tsx`，提供 4 种字幕视觉主题切换、关键词高亮调色、顶部 Title 横幅配置、防搬运水印配置、空镜节奏选择。
- [x] Task 2.2: 改造 `frontend/src/components/VideoPlayer.tsx`，加入顶部横幅层、右上角水印层、并升级字幕层支持高亮词拆分染色与主题样式。
- [x] Task 2.3: 在 `frontend/src/pages/VideoEditor.tsx` 中集成 `StrategyStudio`，增加工作模式切换（轨道剪辑 vs 策略实验），打通状态即时同步与服务端保存。
- [x] Task 2.4: 运行 `pnpm --prefix frontend run build` 确保前端类型与组件打包无误。

---

## Phase 3: 全链路回归与验证验收 (Verification & Deliver)

- [x] Task 3.1: 运行全量 `pytest` 确保所有 28 个测试 100% 通过。
- [x] Task 3.2: 验证浏览器端实时切换 4 种策略主题并在竖屏播放器中呈现高亮与横幅，确认与后端导出效果一致。
- [x] Task 3.3: 提交 Git 代码更新并沉淀 Walkthrough 成果报告。