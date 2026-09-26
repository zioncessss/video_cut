# Tasks: 场地与教学空镜地区车牌标签管理与精准匹配 (014-broll-plate-region)

**Input**: Design documents from `specs/014-broll-plate-region/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md)  
**Branch**: `014-broll-plate-region`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立浙江 11 地市与车牌常识基础字典（前后端对齐）

- [X] T001 [P] Define Zhejiang 11 cities catalog and district mapping in backend/app/core/plate_regions.py
- [X] T002 [P] Define Zhejiang 11 cities constant list and plate badge helpers in frontend/src/constants/regions.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 实体与存储层演进，为后续所有用户故事提供数据底座

- [X] T003 Add plate_region to Material and target_region to Project in backend/app/models/entities.py
- [X] T004 Implement idempotent SQLite schema migration for plate_region and target_region in backend/app/db/session.py
- [X] T005 Extend MaterialRepository to support plate_region persistence, filtering, and updating in backend/app/db/repository.py
- [X] T006 [P] Add contract tests for schema migration and region models in tests/test_plate_region_schema.py

**Checkpoint**: 数据库与底层模型已具备车牌地区持久化能力，可并行启动用户故事

---

## Phase 3: User Story 1 - 场地与教学空镜上传时标注地区车牌 (Priority: P1) 🎯 MVP

**Goal**: 用户在上传或批量导入“场地空镜”与“教学空镜”时，可通过单选下拉框指定所属浙江地市（浙A ~ 浙L），元数据完整持久化。  
**Independent Test**: 在素材库切换到场地空镜，选择 `浙E · 湖州` 并导入视频，断言素材库返回该素材包含 `plate_region: "浙E·湖州"`。

### Tests for User Story 1
- [X] T007 [P] [US1] Create unit tests for upload and local-import with plate_region in tests/test_material_region_api.py

### Implementation for User Story 1
- [X] T008 [US1] Update upload and local-import endpoints to accept plate_region parameter in backend/app/api/editor.py
- [X] T009 [P] [US1] Update uploadMaterial and importLocalMaterial API service functions with plate_region in frontend/src/services/api.ts
- [X] T010 [US1] Add single-select region dropdown to upload toolbar for venue and lesson tabs in frontend/src/pages/AssetLibrary.tsx
- [X] T011 [US1] Connect native file dialog and drag-and-drop actions to pass selected plate_region in frontend/src/pages/AssetLibrary.tsx

**Checkpoint**: MVP 闭环达成，新上传的场地与教学素材具备完整的属地车牌标签。

---

## Phase 4: User Story 2 - 素材库卡片徽章展示与地区快速修改 (Priority: P2)

**Goal**: 素材卡片上直观呈现车牌地区徽章，支持原地点击下拉切换所属城市，提供二级地市筛选。  
**Independent Test**: 点击已入库素材卡片上的车牌徽章，原地切换为 `浙A · 杭州`，刷新页面验证持久化保存生效。

### Tests for User Story 2
- [X] T012 [P] [US2] Add unit tests for in-place region update API in tests/test_material_region_update.py

### Implementation for User Story 2
- [X] T013 [US2] Implement PATCH /api/v1/materials/{id}/region endpoint for in-place tag updates in backend/app/api/editor.py
- [X] T014 [P] [US2] Implement updateMaterialRegion API service function in frontend/src/services/api.ts
- [X] T015 [US2] Render city plate badge on material cards with click-to-edit dropdown in frontend/src/pages/AssetLibrary.tsx
- [X] T016 [US2] Add secondary region filter bar to material list in frontend/src/pages/AssetLibrary.tsx

**Checkpoint**: 素材库具备完整的属地展示、原地修改治理与多维度筛选能力。

---

## Phase 5: User Story 3 - AI 全自动识别口播城市与绝对防穿帮分镜匹配 (Priority: P3)

**Goal**: ASR 文本自动推导视频目标城市（免人工手动配置），分镜调度仅抽取同城素材，不足时同城复用或保留口播真人，实现 100% 绝对防穿帮。  
**Independent Test**: 导入含“湖州长兴考场”的口播视频，素材库混有浙A与浙E素材，启动智能初剪，断言目标城市自动判定为 `浙E·湖州`，所有空镜素材 100% 仅来自浙E，0 跨区穿帮。

### Tests for User Story 3
- [X] T017 [P] [US3] Create unit tests for ASR geographic deduction algorithm in tests/test_plate_region_deduction.py
- [X] T021 [P] [US3] Create integration tests for zero-leak b-roll allocation in tests/test_scene_decision_plate_region.py

### Implementation for User Story 3
- [X] T018 [US3] Implement deduce_target_region scoring algorithm with district and test-center keywords in backend/app/core/plate_regions.py
- [X] T019 [US3] Integrate ASR region deduction into analyze_and_cut pipeline to set project target_region in backend/app/api/editor.py
- [X] T020 [US3] Implement strict same-city b-roll candidate filtering and anti-leak fallback in backend/app/native_engine/scene_decision.py and backend/app/api/editor.py
- [X] T022 [US3] Display auto-detected target city badge in project header in frontend/src/pages/VideoEditor.tsx

**Checkpoint**: 全链路智能闭环达成，AI 自动感知地理常识，剪辑成片绝无异地车牌穿帮。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 全链路集成回归与文档验收

- [X] T023 Verify end-to-end user journeys following quickstart guide in specs/014-broll-plate-region/quickstart.md
- [X] T024 Run full test suite regression covering database integrity and pipeline tests in tests/

---

## Dependencies & Execution Order

### Phase Dependencies
1. **Phase 1 (Setup)**: 独立无前置依赖，前后端常量定义可并行启动。
2. **Phase 2 (Foundational)**: 依赖 Phase 1，阻塞所有 User Stories。
3. **Phase 3 (US1 - 上传标注)**: 依赖 Phase 2，可独立交付 MVP。
4. **Phase 4 (US2 - 展示与改签)**: 依赖 Phase 3（依赖素材具有 `plate_region` 属性）。
5. **Phase 5 (US3 - ASR 推导与防穿帮)**: 依赖 Phase 2 与 Phase 3，实现剪辑闭环。
6. **Phase 6 (Polish)**: 依赖全部 User Stories 完成。

### Parallel Opportunities
- `T001` 与 `T002` 可完全并行开发；
- `T006`、`T007`、`T012`、`T017`、`T021` 测试用例可提前并行编写；
- 前端组件任务与后端 API 任务在契约确定后可并行推进。

---

## Implementation Strategy

### MVP First (Phase 1 ~ Phase 3)
1. 先落实字典常数与数据库迁移（`T001 ~ T006`）；
2. 交付素材上传单选功能（`T007 ~ T011`）；
3. **MVP 验证**：在素材库能为新录入素材打上 `浙A` 至 `浙L` 车牌标签。

### Incremental Delivery
1. MVP 交付后，快速落地卡片徽章与原地改签治理功能（Phase 4, `T012 ~ T016`）；
2. 随后接入 ASR 全自动推导与分镜 0 穿帮过滤（Phase 5, `T017 ~ T022`）；
3. 运行端到端验收与全量单测回归（Phase 6, `T023 ~ T024`）。
