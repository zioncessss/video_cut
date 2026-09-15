# Tasks: 真实 Codex Harness 驱动的智能纠错与自然语言剪辑工作台

**Branch**: `002-real-codex-harness` | **Date**: 2026-09-16 | **Spec**: [specs/002-real-codex-harness/spec.md](spec.md)

## Phase 1: Setup & Environment Initialization
- [X] T001 验证并确保本地 `storage/settings.json` 的读写支持与 schema 扩展 (`backend/app/core/config.py`)
- [X] T002 扩展 Harness 数据结构模型定义与返回结构 (`backend/app/harness_bridge/base.py`)

## Phase 2: Foundational & Core Subprocess Engine
- [X] T003 实现 Codex CLI 子进程执行器（包含 `stdin=DEVNULL` 防挂起、35s 超时控制与 `-o <temp_file>` 结构化 JSON 提取）(`backend/app/harness_bridge/codex.py`)
- [X] T004 实现 Codex CLI 异常与超时自动降级机制（平滑回退至 `EmbeddedHarnessBridge` 并标记引擎状态）(`backend/app/harness_bridge/codex.py`)
- [X] T005 编写 Codex 桥接器专有单元测试集 (`tests/test_codex_bridge.py`)

## Phase 3: User Story 1 - 设置中心持久化与 Codex 连通性测试 (Priority: P1)
- [X] T006 [US1] 在后端添加 `POST /api/settings/test-harness` 探针接口，执行最小 ping 测试并返回耗时与模型信息 (`backend/app/api/settings.py`)
- [X] T007 [US1] 增强前端设置页：新增「测试连通性」按钮、状态加载、实时延迟显示与可选模型覆盖输入框 (`frontend/src/pages/Settings.tsx`)
- [X] T008 [US1] 前端 API 服务新增 `testHarness` 接口封装 (`frontend/src/services/api.ts`)

## Phase 4: User Story 2 - 真实 Codex CLI 口播字幕智能纠错 (Priority: P1)
- [X] T009 [US2] 在 `CodexHarnessBridge` 中实现 `correct_subtitles`：注入驾校专有词库与上下文，调度 Codex CLI 返回纠错详情 (`backend/app/harness_bridge/codex.py`)
- [X] T010 [US2] 升级后端纠错接口 `POST /api/editor/correct`：返回结构化纠正字幕、原词/新词变更对照列表及耗时 (`backend/app/api/editor.py`)
- [X] T011 [US2] 前端剪辑工作台接入纠错变更展示：在字幕卡片高亮显示修改点并弹出详细审阅面板 (`frontend/src/pages/VideoEditor.tsx`)

## Phase 5: User Story 3 - 全能自然语言微调（文案润色/空镜重排/节奏微调） (Priority: P1)
- [X] T012 [US3] 在 `CodexHarnessBridge` 中实现 `apply_natural_instruction`：组装当前字幕、素材库元数据与用户指令，解析生成全能微调响应 (`backend/app/harness_bridge/codex.py`)
- [X] T013 [US3] 升级后端微调接口 `POST /api/instruction/apply`：处理并应用更新后的字幕与 B-roll 关联 (`backend/app/api/instruction.py`)
- [X] T014 [US3] 前端自然语言微调输入区联动：支持回车/点击发送，实时应用返回的字幕与空镜替换，并展示智能体操作说明 (`frontend/src/pages/VideoEditor.tsx`)

## Phase 6: User Story 4 - 剪辑工作台引擎状态可视化感知 (Priority: P2)
- [X] T015 [US4] 剪辑工作台顶部状态栏增加「当前 Harness 引擎状态徽章」（展示 Codex 活跃模型或降级 Embedded 状态）(`frontend/src/pages/VideoEditor.tsx`)

## Phase 7: Polish & End-to-End Validation
- [X] T016 运行全量自动化测试套件 `pytest tests/test_codex_bridge.py` 验证连通性、纠错、微调与降级机制
- [X] T017 运行前端构建检查 `pnpm run build` 确保无 TypeScript 或样式类型错误