# Tasks: 真实人物口播视频滤镜画质调优与最佳剪辑效果 (portrait-filter-enhancement)

**Feature Branch**: `010-portrait-filter-enhancement`  
**Input Documents**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [contracts/filter_presets_api.json](./contracts/filter_presets_api.json), [research.md](./research.md)

---

## Phase 1: Setup & Data Models (基础设施与数据结构)

- [X] T001 [P] 扩展剪辑策略数据模型 `EditingStrategy`，新增 `filter_preset` 与 `filter_strength` 字段于 `backend/app/models/entities.py`
- [X] T002 [P] 编写口播滤镜专属单元与集成测试框架于 `tests/test_portrait_filters.py`

---

## Phase 2: Foundational Native Engine (底层滤镜与渲染引擎)

- [X] T003 定义 `PORTRAIT_PRESETS` 参数字典（包含 `clean_natural`, `crisp_hd`, `warm_radiant`, `original` 4大黄金预设），实现参数校验与根据强度线性插值函数 `build_portrait_filter_chain()` 于 `backend/app/native_engine/ffmpeg_filter.py`
- [X] T004 升级 `FFmpegFilterComposer.build_color_normalize_filter()`，确保口播滤镜链挂载在 `scale` 之后、`pad` 居中补黑边之前（彻底防止居中黑边被亮化变灰）于 `backend/app/native_engine/ffmpeg_filter.py`
- [X] T005 升级 `FFmpegFilterComposer.compose_jl_cut()`，贯通单视频转码流、粗剪切片序列（`kept_spans`）拼接以及多空镜混剪流，使其在读取 `strategy.filter_preset` 与 `strategy.filter_strength` 后无缝压制高清调优成片于 `backend/app/native_engine/ffmpeg_filter.py`

---

## Phase 3: User Story 1 (P1) - 滤镜预设与策略 API (Backend Endpoints)

**Goal**: 前后端打通滤镜预设元数据查询与工程策略更新。  
**Independent Test**: 请求 `GET /api/editor/filter-presets` 返回规范预设信息；保存策略后成功持久化到 SQLite 数据库。

- [X] T006 [US1] 在 `backend/app/api/editor.py` 中新增 `GET /api/editor/filter-presets` 接口，暴露预设 ID、中文名称、适用场景描述与推荐标签
- [X] T007 [US1] 确保 `PUT /api/editor/{project_id}/strategy` 与 `POST /api/editor/analyze-and-cut` 能正确接受、校验并持久化 `filter_preset` 和 `filter_strength` 字段于 `backend/app/api/editor.py`

---

## Phase 4: User Story 2 (P1) - 工作台滤镜控制面板 (Frontend UI)

**Goal**: 剪辑工作台右侧策略面板提供直观的口播滤镜预设选择卡片与强度调节滑块。  
**Independent Test**: 用户点击不同预设按钮卡片或拖拽强度滑块，策略即时保存并在导出视频时生效。

- [X] T008 [US2] 在前端类型定义 `frontend/src/types/index.ts` 中同步 `EditingStrategy` 的 `filter_preset` 与 `filter_strength` 字段
- [X] T009 [US2] 在工作台策略设置组件 `frontend/src/components/editor/StrategySettings.tsx` 中新增“画面调优与口播滤镜”卡片，包含 4 档预设选择（带推荐徽章与说明）及 0%~100% 强度滑块，联动 `updateStrategy` 实时保存

---

## Phase 5: User Story 3 (P2) - 自动化验证与真机实测 (Verification & Testing)

**Goal**: 全面验证各预设参数、插值算法、黑边保护以及真实素材合成导出，确保零光晕、无脏脸、不崩溃。  
**Independent Test**: 运行 pytest 测试全部通过，且使用真实口播素材导出成片。

- [X] T010 [US3] 完善 `tests/test_portrait_filters.py` 中的测试用例：预设完整性、线性插值、original 旁路、黑边防灰、以及真实视频小样 `compose_jl_cut` 导出断言
- [X] T011 [US3] 运行自动化测试与真实视频渲染验证，确认输出成片符合预期

---

## Phase 6: Polish & Documentation (验收与文档维护)

- [X] T012 检查全链路代码风格、类型注解与错误处理，更新 `walkthrough.md` 记录实现成果与验证截帧
