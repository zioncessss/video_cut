# Tasks: MiniMax 统一接管 ASR 语音识别与大模型智能剪辑 (006-minimax-asr-llm)

**Input**: Design documents from `specs/006-minimax-asr-llm/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/api.md`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/api.md`

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)
- Every task includes an explicit file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify development environment, Windows UTF-8 encoding, and dependencies.

- [x] T001 Verify Python and Node environments and test runners in `backend/` and `frontend/`
- [x] T002 [P] Configure environment encoding and execution scripts for Windows UTF-8 in `scripts/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and shared configuration that MUST be complete before ANY user story can proceed.

**⚠️ CRITICAL**: Blocked on Setup completion. All user story implementation depends on these foundational models and configs.

- [x] T003 Update data models with `BrollCueItem`, `BrollCueResponse`, and `broll_target_coverage` in `backend/app/models/entities.py`
- [x] T004 [P] Update MiniMax configuration helpers and constants in `backend/app/core/config.py`

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 - MiniMax 极速语音识别与字级时间戳自然断句 (Priority: P1) 🎯 MVP

**Goal**: 废除 14 字机械硬切，调用 MiniMax `asr-1.0` 接口获取毫秒级逐字声学时间戳，通过词尾标点感知、8~18 字自然意群保护与弹性合并，100% 消除中文词组截半腰斩（“千万不 / 要报”）与孤立微短碎片（<1s），并支持断网离线无缝降级 Faster-Whisper。

**Independent Test**: 运行 `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_minimax_asr.py -v`，断言 8~18 字自然意群完整断句、无动宾短语腰斩、首尾词戳精确对齐，且云端异常时 100% 自动平滑降级本地 Faster-Whisper。

### Tests for User Story 1

- [x] T005 [P] [US1] Write unit tests for word trailing punctuation extraction and no mid-word chopping in `tests/test_minimax_asr.py`

### Implementation for User Story 1

- [x] T006 [US1] Refactor `parse_minimax_response` in `backend/app/native_engine/asr_runner.py` to strip trailing punctuation from words and remove `curr_len >= 14` hard break
- [x] T007 [US1] Refactor `split_into_readable_segments` in `backend/app/native_engine/asr_runner.py` to support natural clause segmentation with punctuation & conjunction boundary rules (8~18 chars)
- [x] T008 [US1] Update `merge_short_segments` in `backend/app/native_engine/asr_runner.py` to elastically absorb micro-fragments (<1.0s) and allow up to 18 chars for complete clauses
- [x] T009 [US1] Verify cloud-to-local automatic fallback mechanism in `backend/app/native_engine/asr_runner.py`

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently as the core MVP.

---

## Phase 4: User Story 2 - MiniMax 稀疏分镜决策与双层 60%~70% 编排引擎 (Priority: P1)

**Goal**: 将分镜大模型契约重构为稀疏剪辑指示清单（`broll_cues`，Token < 300，耗时 < 3s），并引入“强相关语义精准锚定 + 自由段落自适应随机铺底”双层编排机制，严格保障开场 1.8s 真人、报价手势、结尾 CTA 三大禁切红线，硬性确保 1~2 分钟成片达到 60%~70% 黄金空镜覆盖率（支持手动调整）。

**Independent Test**: 运行 `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_scene_decision_cue.py -v`，断言稀疏 Cue Sheet 契约解析正确，三大禁切区 100% 保留口播真人，成片空镜总时长严格收敛于片长的 60%~70% 黄金区间。

### Tests for User Story 2

- [x] T010 [P] [US2] Create unit tests for sparse Cue Sheet parsing, 60%~70% dual-layer coverage, and prohibited zone guards in `tests/test_scene_decision_cue.py`

### Implementation for User Story 2

- [x] T011 [US2] Refactor `build_scene_decision_prompt` in `backend/app/harness_bridge/prompting.py` to output sparse `broll_cues` JSON and remove negative restraint rules
- [x] T012 [US2] Update `decide_scenes` in `backend/app/harness_bridge/api_engine.py` to call MiniMax with sparse Cue Sheet prompt and parse `broll_cues`
- [x] T013 [US2] Implement physical word timestamp snapping and prohibited zone guard filtering in `backend/app/native_engine/scene_decision.py`
- [x] T014 [US2] Implement dual-layer free-body random pacing slot fill in `backend/app/native_engine/scene_decision.py` to guarantee 60%~70% target coverage
- [x] T015 [US2] Update `fallback_keyword_rules` in `backend/app/native_engine/scene_decision.py` to apply the dual-layer pacing slot fill during offline fallback
- [x] T016 [US2] Integrate sparse Cue Sheet decisions and dual-layer B-roll placement into the editing pipeline in `backend/app/api/editor.py`

**Checkpoint**: At this point, User Stories 1 AND 2 are fully integrated, providing rapid STT, natural subtitles, and 60%~70% B-roll pacing.

---

## Phase 5: User Story 3 - 设置中心 MiniMax 统一凭据配置与双通道连通性检测 (Priority: P2)

**Goal**: 在系统设置中集中配置 MiniMax API Key、选择模型名称（`MiniMax-Text-01`）与启用云端极速 ASR，支持一键点击「测试连通性」同时检测 LLM（TTFT 延迟）与 ASR 双通道健康状态，严格保护 API Key 不在前端明文下发。

**Independent Test**: 运行 `$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_settings_api.py -v`，断言设置更新生效、GET 接口不返回明文 Key、连通性探测接口正常返回双通道健康状态。

### Tests for User Story 3

- [x] T017 [P] [US3] Add unit and integration tests for unified MiniMax credentials and connectivity probe in `tests/test_settings_api.py`

### Implementation for User Story 3

- [x] T018 [US3] Implement dual-channel health probe endpoint (`/api/v1/settings/test-connection`) in `backend/app/api/settings.py`
- [x] T019 [US3] Update frontend API client for connectivity testing in `frontend/src/services/api.ts`
- [x] T020 [US3] Update Settings UI to support MiniMax provider, ASR toggle, and one-click connectivity diagnostics in `frontend/src/pages/Settings.tsx`

**Checkpoint**: All three user stories are functional and testable end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end regression validation, cross-cutting checks, and documentation updates.

- [x] T021 [P] Run full backend test suite in `tests/` with Windows UTF-8 environment settings
- [x] T022 [P] Verify frontend production build with `pnpm build` in `frontend/`
- [x] T023 Run end-to-end editing pipeline regression in `tests/test_all_flows.py` to verify 0 word-chopping and 60%~70% B-roll
- [x] T024 Update user documentation and changelog in `README.md` and `docs/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
  - Phase 3 (US1) can start immediately after Phase 2.
  - Phase 4 (US2) depends on Phase 2; consumes the natural subtitle segments produced by Phase 3 for full end-to-end execution.
  - Phase 5 (US3) depends on Phase 2; can be developed in parallel with US1/US2.
- **Polish (Phase 6)**: Depends on all user stories being complete.

### User Story Dependencies

- **User Story 1 (P1 - ASR & Subtitle Chunking)**: Depends only on Foundational (Phase 2). Delivers standalone ASR and natural subtitle chunking.
- **User Story 2 (P1 - Cue Sheet & Dual-Layer Pacing)**: Depends on Foundational (Phase 2). Reads subtitle structures from US1 for video pipeline integration, but its core logic (Cue Sheet parsing, dual-layer slot filling) can be developed and unit-tested independently.
- **User Story 3 (P2 - Settings & Diagnostics)**: Depends on Foundational (Phase 2). Interacts with config and settings endpoints independently.

### Within Each User Story

- Tests written first, verified failing or ready.
- Data models updated before services/runners.
- Core engine algorithms implemented before pipeline integration.
- Story complete and validated before moving to cross-cutting concerns.

### Parallel Opportunities

- **Setup**: `T001` and `T002` can run concurrently.
- **Foundational**: `T003` and `T004` can run concurrently.
- **Phase 3 (US1)**: Test task `T005` can be written while reviewing implementation.
- **Phase 4 (US2)**: Test task `T010` can be created in parallel with prompt refactoring (`T011`).
- **Phase 5 (US3)**: Frontend UI (`T020`) and Backend endpoint (`T018`) can proceed in parallel once API contract is fixed.
- **Phase 6 (Polish)**: `T021` (backend tests) and `T022` (frontend build) can execute in parallel.

---

## Parallel Execution Examples

### User Story 1 (ASR & Subtitles)

```bash
# Run US1 tests
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_minimax_asr.py -v
```

### User Story 2 (Cue Sheet & Dual-Layer Pacing)

```bash
# Develop prompt and test contract
# Task T011: Refactor build_scene_decision_prompt in backend/app/harness_bridge/prompting.py
# Task T010: Create unit tests in tests/test_scene_decision_cue.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Implement Phase 3 (User Story 1: MiniMax STT + 8~18 char natural chunking + no word chopping).
3. **STOP and VALIDATE**: Run `tests/test_minimax_asr.py` with sample audio to confirm 0 mid-word splits and 2~5s transcription.
4. Deploy/commit MVP increment.

### Incremental Delivery

1. Foundation ready (Phase 1 + 2).
2. MVP delivered: Fast ASR & clean subtitles (Phase 3).
3. Core Feature delivered: Sparse Cue Sheet & 60%~70% B-roll coverage (Phase 4).
4. User Experience delivered: Settings UI & dual-channel diagnostics (Phase 5).
5. Quality Gate: Full regression test suite and frontend build pass (Phase 6).
