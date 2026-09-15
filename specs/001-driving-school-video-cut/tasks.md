---
description: "Task list for 001-driving-school-video-cut feature implementation"
---

# Tasks: 驾校短视频网感剪辑工作台 (混合双引擎架构)

**Input**: Design documents from `specs/001-driving-school-video-cut/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)  
**Prerequisites**: Python 3.11+, FFmpeg/FFprobe in system PATH, Node 18+  
**Architecture**: 固化执行层 (Native Hardcoded) + 高阶套壳层 (Harness Wrapper) + 浅色调 C 端 Web/桌面外壳  

## Format: `[ID] [P?] [Story] Description`
- **[P]**: 可并行执行的任务（不同文件，无直接上下游依赖）
- **[Story]**: 所属用户故事（如 US1, US2, US3, US4, US5, US6）
- 必须包含确切的文件路径与修改范围

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 初始化前后端工程目录结构、依赖配置与跨平台路径规范。

- [X] T001 创建物理项目骨架目录：`backend/`, `frontend/`, `storage/materials/{talking_head,venue,medical,lesson}/`, `tests/`
- [X] T002 初始化后端 Python 依赖配置在 `backend/requirements.txt`（包含 `fastapi`, `uvicorn`, `faster-whisper`, `ffmpeg-python`, `psutil`, `pydantic`, `pywebview`）
- [X] T003 初始化前端 Vite + React + Tailwind CSS + Lucide 图标库工程在 `frontend/package.json`
- [X] T004 [P] 配置基础环境变量与路径常量在 `backend/app/core/config.py`（跨平台兼容 Windows / macOS 目录分隔符）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心数据模型、Harness 抽象基类与存储底层，为所有用户故事提供基础设施。

- [X] T005 实现核心 Pydantic 实体模型在 `backend/app/models/entities.py`（参照 `data-model.md` 中的 `Material`, `SubtitleSegment`, `BrollReplacement`, `CutProject`, `BatchJob`）
- [X] T006 [P] 实现物理存储服务与元数据探测器在 `backend/app/native_engine/storage.py`（利用 `ffprobe` 提取时长、分辨率、帧率）
- [X] T007 [P] 实现 `BaseHarnessBridge` 抽象基类在 `backend/app/harness_bridge/base.py`（参照 `contracts/harness-adapter.md` 定义接口）
- [X] T008 [P] 实现硬件资源侦测与并发槽位计算在 `backend/app/core/resource.py`（基于 `psutil` 侦测 CPU/RAM/GPU，计算 `MaxWorkers`）
- [X] T009 搭建 FastAPI 主服务与 CORS 中间件在 `backend/app/main.py`

---

## Phase 3: User Story 1 - 基础素材上传与四分目录管理 (Priority: P1)

**Goal**: 实现口播、场地、体检、教学 4 类视频素材的分类上传、物理落盘与元数据卡片读取。  
**Independent Test**: 用户拖拽视频至不同类别，文件落盘到 `storage/materials/{category}/`，前端展示视频时长与分辨率。

- [X] T010 [P] [US1] 编写素材上传与检索单元测试在 `tests/test_storage.py`
- [X] T011 [US1] 实现素材上传与列表 REST 接口在 `backend/app/api/materials.py`（严格遵循 `contracts/web-api.md`）
- [X] T012 [P] [US1] 实现前端素材库页面在 `frontend/src/pages/AssetLibrary.tsx`（提供 4 个分类拖拽上传区，现代浅色卡片布局）
- [X] T013 [US1] 联调前后端素材流：支持上传进度、视频缩略图与时长展示

---

## Phase 4: User Story 2 - 口播音频 ASR 识别与 LLM 专有词纠偏 (Priority: P1)

**Goal**: 提取口播音频，毫秒级转写文字时间戳（Native ASR），并通过 Harness/LLM 上下文纠正驾校特定错别字。  
**Independent Test**: 上传包含“科二/倒库/体检”口语的口播，验证输出带有纠偏后的时间戳字幕列表。

- [X] T014 [P] [US2] 编写 ASR 与 LLM 纠错测试在 `tests/test_asr_llm.py`
- [X] T015 [US2] 实现固化 ASR 引擎在 `backend/app/native_engine/asr_runner.py`（基于 `faster-whisper`，自动降级 CPU/GPU）
- [X] T016 [US2] 实现 Harness 纠偏适配器在 `backend/app/harness_bridge/embedded.py` 与 `backend/app/harness_bridge/codex.py`（注入驾校领域词库与 Few-Shot Prompt）
- [X] T017 [US2] 编写关键词自动匹配器在 `backend/app/native_engine/keyword_matcher.py`（将校正文本与场地/体检/练车词表比对并打标）

---

## Phase 5: User Story 3 - 关键词驱动空镜智能替换与 J/L-Cut 双轨合成 (Priority: P1) 🎯 MVP

**Goal**: 保持口播原声持续不中断，在命中的关键词区间自动将画面无缝替换为空镜头素材（声画分离），压制成品视频。  
**Independent Test**: 调用合成接口，生成一段带背景原声 + 空镜切入 + 底部高亮字幕的 9:16 视频。

- [X] T018 [P] [US3] 编写多轨 FFmpeg 复合滤镜单元测试在 `tests/test_composer.py`
- [X] T019 [US3] 实现确定性 FFmpeg 滤镜合成器在 `backend/app/native_engine/ffmpeg_filter.py`（组装 `filter_complex`，实现 J/L-Cut 声画分离与自动缩放裁剪至 1080x1920）
- [X] T020 [US3] 实现 `.ass` 高质感字幕生成器在 `backend/app/native_engine/subtitle_styler.py`（现代粗无衬线字体，关键词高亮样式）
- [X] T021 [US3] 实现剪辑工程接口在 `backend/app/api/editor.py`（触发解析、合成与流式进度回传）

---

## Phase 6: User Story 4 - 交互式可视化预览与双轨字幕编辑器 (Priority: P2)

**Goal**: C 端工作台界面：左侧视频带字幕播放器，右侧时间轴字幕可编辑列表，底部 AI 快速调整指令框。  
**Independent Test**: 在前端修改右侧字幕文本，播放器即时联动定位；在底部输入指令，触发局部更新。

- [X] T022 [P] [US4] 实现左侧竖屏播放器组件在 `frontend/src/components/VideoPlayer.tsx`（支持时间点定位与画质切换）
- [X] T023 [P] [US4] 实现右侧字幕时间轴卡片列表在 `frontend/src/components/SubtitleList.tsx`（可点击修改文本、调整区间、显示空镜分类徽章）
- [X] T024 [US4] 实现底部自然语言指令栏与 Harness 套壳微调接口在 `backend/app/api/instruction.py`（用户输入“把第3句换个场地”，调 Harness 解析并更新工程）
- [X] T025 [US4] 组装完整工作台页面在 `frontend/src/pages/VideoEditor.tsx`，联动播放器与时间轴

---

## Phase 7: User Story 5 - 批量混剪与硬件感知并发调度 (Priority: P2)

**Goal**: 一次性批量生成多条视频，自动探测硬件资源计算并发槽位，防止电脑卡死。  
**Independent Test**: 提交 10 个视频混剪任务，观察并发数不超过安全阈值，内存稳定无崩溃。

- [X] T026 [P] [US5] 编写资源限流调度器测试在 `tests/test_resource.py`
- [X] T027 [US5] 实现异步任务队列与自适应信号量在 `backend/app/core/batch_queue.py`（动态依据可用内存节流并发 FFmpeg 进程）
- [X] T028 [US5] 实现批量生产 API 与 WebSocket 实时进度在 `backend/app/api/batch.py`
- [X] T029 [US5] 实现批量生产前端页面在 `frontend/src/pages/BatchCut.tsx`（展示硬件健康状态仪表盘、批量任务进度条与成品打包下载）

---

## Phase 8: User Story 6 - 双端免终端桌面启动封装与 Harness 切换 (Priority: P3)

**Goal**: 适配 Windows & macOS 双击免终端启动，设置页支持自由切换底层 Harness（Codex / ZCode / Embedded）。  
**Independent Test**: 双击启动脚本，无需任何终端直接弹出桌面窗口；设置页切换 Harness 即时生效。

- [X] T030 [P] [US6] 实现桌面窗体引导器在 `launcher.py`（利用 `pywebview` 托管本地前端与静默后端）
- [X] T031 [P] [US6] 编写 Windows 静默启动脚本 `start_windows.vbs` 与 macOS 启动脚本 `start_mac.command`
- [X] T032 [US6] 实现 Harness 引擎切换与配置页面在 `frontend/src/pages/Settings.tsx` 及 `backend/app/api/settings.py`

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 视觉优化、空音频/缺失素材异常边界防御与体验打磨。

- [X] T033 [P] 全局浅色调视觉美化与细节打磨（抗锯齿字体、毛玻璃微阴影、品牌蓝色系对齐）
- [X] T034 完善异常兜底：素材缺失时平滑保留口播画面、空音轨拦截提示在 `backend/app/native_engine/fallback.py`
- [X] T035 端到端跑通 `quickstart.md` 中所有验证用例
