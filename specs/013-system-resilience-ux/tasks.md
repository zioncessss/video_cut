# Tasks: 系统安全边界、状态一致性与交互体验加固 (013-system-resilience-ux)

**Input**: Design documents from `/specs/013-system-resilience-ux/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)  
**Prerequisites**: `plan.md`, `spec.md`, `data-model.md`, `contracts/`  
**Tests**: 包含关键生命周期、容错与状态机流转的自动化回归测试（遵照 AGENTS.md 真实执行与防假运行准则）  
**Organization**: 按用户故事（User Story）优先级分阶段组织，每个阶段可独立交付、独立测试。

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: 可并行执行（不同文件，无未决前置依赖）
- **[Story]**: 所属用户故事标签（如 `[US1]`, `[US2]`, `[US3]`）

---

## Phase 1: Setup (共享基础配置)

**Purpose**: 初始化基础枚举与依赖定义

- [x] T001 [P] 扩展作业生命周期状态枚举 `BatchJobStatus`（增加 `canceled`, `interrupted`）于 `backend/app/models/entities.py`
- [x] T002 [P] 扩展前端数据接口定义 `BatchJobItem` 与控制接口签名于 `frontend/src/services/api.ts`

---

## Phase 2: Foundational (基础设施支撑)

**Purpose**: 为所有 User Story 奠定底座，阻塞后续故事

- [x] T003 在 `backend/app/db/repository.py` 中为 `BatchJobRepository` 新增启动自愈巡检方法 `cleanup_zombie_running_jobs()`
- [x] T004 在 `backend/app/main.py` 的应用 `lifespan` 启动钩子中挂载 `cleanup_zombie_running_jobs()`，将遗留僵尸批次置为 `interrupted`
- [x] T005 [P] 在 `frontend/src/services/api.ts` 中封装支持 `AbortSignal` 的 `analyzeAndCutVideo` 与 `fetchProjectByMaterial`

**Checkpoint**: 基础枚举、自愈基础设施与客户端 Abort 签名就绪，用户故事可独立开展。

---

## Phase 3: User Story 1 - 数据生命周期安全与幽灵工程消除 (Priority: P0) 🎯 MVP

**Goal**: 彻底消除素材删除后的任务目录残留与 `_heal_from_disk` 幽灵复活，并在前端引入 `AbortController` 消除异步竞态覆盖。

**Independent Test**: 执行 `pytest tests/test_ghost_project_elimination.py -v` 验证压制成片后删除素材，物理目录被删除且重启后绝不复活；通过 UI 快速切换素材验证无状态污染。

### Tests for User Story 1 ⚠️
- [x] T006 [P] [US1] 编写幽灵工程消除端到端自动化测试于 `tests/test_ghost_project_elimination.py`

### Implementation for User Story 1
- [x] T007 [US1] 改造 `backend/app/native_engine/project_storage.py` 中的 `delete_project_by_material`，删除数据库前显式调用 `_cleanup_project_files(p)` 彻底删除任务目录与清单文件
- [x] T008 [US1] 加固 `backend/app/native_engine/project_storage.py` 中的 `_heal_from_disk()`，扫描任务清单时强校验 `talking_head_id` 必须存在于 `materials` 表，否则就地销毁残余目录禁止入库
- [x] T009 [US1] 加固 `backend/app/native_engine/storage.py` 中的 `delete_material()`，当删除素材为空镜时，联动将存量工程的 `subtitles.broll_material_id` 与对应 `broll_replacements` 进行解绑置空保护
- [x] T010 [US1] 在 `frontend/src/pages/VideoEditor.tsx` 中为初剪与工程载入引入 `abortControllerRef`，在素材切换与页面注销时主动取消未决 Promise，忽略 Cancelled 错误

**Checkpoint**: User Story 1 具备独立测试条件，磁盘清理闭环，幽灵复活率与竞态覆盖率降为 0。

---

## Phase 4: User Story 2 - 故障容错韧性与批量混剪管控 (Priority: P1)

**Goal**: 为 MiniMax ASR 引入 3 次指数退避重试，为批量混剪提供取消批次、单项失败重试接口及 UI 控制。

**Independent Test**: 执行 `pytest tests/test_asr_retry.py` 验证 ASR 遇到 502/Timeout 自动重试；执行 `pytest tests/test_batch_lifecycle_control.py` 验证取消与重试失败项接口。

### Tests for User Story 2 ⚠️
- [x] T011 [P] [US2] 编写 MiniMax ASR 瞬时网络故障重试单测于 `tests/test_asr_retry.py`
- [x] T012 [P] [US2] 编写批量混剪取消与重试集成测试于 `tests/test_batch_lifecycle_control.py`

### Implementation for User Story 2
- [x] T013 [US2] 在 `backend/app/native_engine/asr_runner.py` 中为 `transcribe_minimax` 封装 3 次指数退避重试机制（退避间隔 1s, 2s, 4s，覆盖 5xx/429/Timeout/网络错误）
- [x] T014 [US2] 在 `backend/app/api/batch.py` 中重构并发调度引擎，将每个 item worker 绑定至可取消的 `asyncio.Task` 字典
- [x] T015 [US2] 在 `backend/app/api/batch.py` 中新增 `POST /batch/jobs/{job_id}/cancel` 接口，支持用户主动取消运行中与排队中条目
- [x] T016 [US2] 在 `backend/app/api/batch.py` 中新增 `POST /batch/jobs/{job_id}/retry-failed` 接口，仅将 `status == 'failed'` 的条目重新压入执行槽位
- [x] T017 [US2] 在 `frontend/src/services/api.ts` 中实现 `cancelBatchJob` 与 `retryFailedBatchJob` 请求方法
- [x] T018 [US2] 在 `frontend/src/pages/BatchCut.tsx` 批次卡片中增加“取消批次”与“重试失败项”交互按钮与状态刷新

**Checkpoint**: User Story 2 独立功能就绪，网络瞬时抖动自愈，批量作业具备完备的生命周期控制。

---

## Phase 5: User Story 3 - 长任务真实进度与阶段感知 (Priority: P2)

**Goal**: 连通前端初剪与后端细粒度进度轮询，打造生动的四阶段指示条；在批量混剪中渲染真实进度条与错误 Tooltip，彻底释放真实错误。

**Independent Test**: 在 `/editor` 点击初剪观察步骤条平滑步进；在 `/batch` 观察进行中条目的进度条推进，断言控制台与弹窗透出真实错误。

### Implementation for User Story 3
- [x] T019 [US3] 加固 `backend/app/api/editor.py` 中的 `_pipeline_progress` 进度更新，确保 `analyze_and_cut` 各阶段均以 `req.talking_head_id` 和 `project.id` 双键更新，并在失败时落真实错误
- [x] T020 [US3] 在 `frontend/src/pages/VideoEditor.tsx` 中创建初剪轮询定时器（800ms），在 `handleOneClickCutAndCorrect` 期间轮询 `fetchProjectProgress`，初剪结束或失败时清理定时器
- [x] T021 [US3] 在 `frontend/src/pages/VideoEditor.tsx` 的剪辑台顶部或处理遮罩中渲染四阶段指示条组件（抽取音频 15% → 语音识别 45% → AI专词纠偏 70% → 双层分镜 90% → 完成 100%）
- [x] T022 [US3] 优化 `frontend/src/pages/VideoEditor.tsx` 错误处理，废除“智能剪辑失败，请确保后端服务正常运行”硬编码，统一透出 `err?.response?.data?.detail`
- [x] T023 [US3] 改造 `frontend/src/pages/BatchCut.tsx` 队列条目渲染，消费 `it.progress` 渲染动态 ProgressBar，并在条目为 `failed` 时渲染错误详情展开卡片或 Tooltip
- [x] T024 [US3] 修复 `frontend/src/pages/BatchCut.tsx:loadData` 中的 `list.slice(0, 10)` 截断缺陷，确保活跃批次全量获取详情更新

**Checkpoint**: User Story 3 独立功能就绪，长耗时链路全程可视可控，彻底摆脱假死感知。

---

## Phase 6: Polish & Cross-Cutting Concerns (收尾与全链路回归)

**Purpose**: 全系统端到端验证与质量加固

- [x] T025 [P] 运行 `pytest tests/ -v` 确保全套后端单测与集成测试 100% 绿灯通过
- [x] T026 按照 `specs/013-system-resilience-ux/quickstart.md` 逐一手工复核 5 大核心端到端场景
- [x] T027 [P] 清理废弃的无用调试代码，执行代码质量检查

---

## Dependencies & Execution Order

### Phase Dependencies
1. **Phase 1 (Setup)**: 无依赖，立即开始
2. **Phase 2 (Foundational)**: 依赖 Phase 1，完成后解锁所有 User Story
3. **Phase 3 (User Story 1 - P0 MVP)**: 依赖 Phase 2，可独立开发测试交付
4. **Phase 4 (User Story 2 - P1)**: 依赖 Phase 2，可与 US1 并行或依次开发
5. **Phase 5 (User Story 3 - P2)**: 依赖 Phase 2，可与 US1/US2 并行或依次开发
6. **Phase 6 (Polish)**: 依赖所有 User Story 完成

### User Story Dependencies
- **US1 (P0)**: 无需其他故事的前置条件，核心聚焦数据与文件安全（MVP 优先交付）
- **US2 (P1)**: 独立于 US1，聚焦网络重试与批处理控制
- **US3 (P2)**: 消费后端的进度字典，前端 UI 体验升级

---

## Implementation Strategy: MVP First

1. **第 1 步 (MVP)**: 完成 Phase 1、Phase 2 与 Phase 3 (User Story 1)；
2. **第 2 步 (验证 MVP)**: 运行 `test_ghost_project_elimination.py`，确认幽灵复活与文件残留 100% 消除；
3. **第 3 步 (容错与批处理)**: 实现 Phase 4 (User Story 2)，赋予系统网络自愈与批量任务取消能力；
4. **第 4 步 (交互升级)**: 实现 Phase 5 (User Story 3)，打通前端 4 步指示条与真实进度展示；
5. **第 5 步 (全量回归)**: 执行 Phase 6 全量测试与端到端验收。
