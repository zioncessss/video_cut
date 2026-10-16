# Tasks: 重新合成全链路深度提速与管线优化

**Feature**: 重新合成全链路深度提速与管线优化  
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup & Baseline Regression

- [x] T001 Run baseline tests `tests/test_render_fast_path.py` and `tests/test_auto_prune_engine.py`

## Phase 2: User Story 1 - 空镜 (B-roll) 管线轻量化与按需接入 (Priority: P1)

- [x] T002 [US1] Refactor `is_hdr_video` in `backend/app/native_engine/ffmpeg_filter.py` with persistent `_hdr_cache` based on path and mtime
- [x] T003 [US1] Eliminate `-stream_loop -1` in `compose_jl_cut` (mode A and mode B) in `backend/app/native_engine/ffmpeg_filter.py` using `-ss` fast seek and finite duration
- [x] T004 [US1] Optimize B-roll filter parts in mode A and B to prevent demuxer lockup

## Phase 3: User Story 2 - CPU 滤镜体系优化与释放 GPU 硬件编码吞吐 (Priority: P1)

- [x] T005 [US2] Verify and fine-tune `build_portrait_filter_chain` and `build_color_normalize_filter` for maximum throughput
- [x] T006 [US2] Create automated test `tests/test_recompose_acceleration.py` asserting B-roll `-ss` inputs and zero redundant `ffprobe` processes

## Phase 4: User Story 3 - 前端交互防抖与落盘 I/O 全链路零阻塞 (Priority: P2)

- [x] T007 [US3] Refactor `handleExecuteRender` in `frontend/src/pages/VideoEditor.tsx` to use `Promise.all` for parallel subtitle and strategy sync
- [x] T008 [US3] Ensure all final video copy paths in `backend/app/api/editor.py` use `os.link` with `shutil.copyfile` fallback

## Phase 5: Polish & Full Verification

- [x] T009 Run `tests/test_recompose_acceleration.py` to assert acceleration behaviors
- [x] T010 Run full test suite (`pytest tests/`) ensuring 100% green without regressions
