# Tasks: 重新合成性能提速与粗剪幽灵碎片跳剪根治

**Feature**: 重新合成性能提速与粗剪幽灵碎片跳剪根治  
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup & Baseline Regression

- [x] T001 Run existing baseline regression tests `tests/test_auto_prune_engine.py` and `tests/test_render_fast_path.py`

## Phase 2: Foundational Engine Upgrades

- [x] T002 [P] Increase merge gap threshold to 0.65s in `_merge_and_sort_spans` in `backend/app/native_engine/prune_engine.py`
- [x] T003 [P] Anchor head idle detection strictly to first non-pruned active subtitle in `analyze_and_prune` in `backend/app/native_engine/prune_engine.py`

## Phase 3: User Story 1 - 彻底消除裁剪遗留的废动作碎片与跳剪 (Priority: P1)

- [x] T004 [US1] Implement adjacent pruned subtitle gap bridging in `backend/app/native_engine/prune_engine.py`
- [x] T005 [US1] Implement Ghost Clip Scrubber in `compute_kept_spans` in `backend/app/native_engine/prune_engine.py`
- [x] T006 [US1] Add unit test `test_ghost_clip_elimination_and_bridge` in `tests/test_auto_prune_engine.py` to assert the 0.52s snippet is purged

## Phase 4: User Story 2 - 重新合成链路极速提速与单次合成通道 (Priority: P1)

- [x] T007 [US2] Optimize scale filter in `build_color_normalize_filter` to `bicubic+accurate_rnd` in `backend/app/native_engine/ffmpeg_filter.py`
- [x] T008 [US2] Refactor `render_project` in `backend/app/api/editor.py` to execute single-pass direct render on clean base cache miss
- [x] T009 [US2] Add single-pass direct render test in `tests/test_render_fast_path.py`

## Phase 5: User Story 3 - 存量工程无损自愈与向后兼容 (Priority: P2)

- [x] T010 [US3] Update `_sync_prune_spans` in `backend/app/api/editor.py` to trigger ghost clip scrubbing on project sync
- [x] T011 [US3] Recompute and self-heal live project `54d31b37-5a5c-4664-b62a-e891a9dbc3d7` in `storage/videocut.db` and verify first subtitle starts at 0.0s

## Phase 6: Polish & Full Verification

- [x] T012 Run full test suite (`pytest tests/`) to guarantee 100% green without regressions
