# Feature Specification: 重新合成全链路深度提速与管线优化 (018-recompose-pipeline-acceleration)

**Feature Branch**: `018-recompose-pipeline-acceleration`  
**Created**: 2026-10-16  
**Status**: Draft  
**Input**: 全面治理造成「重新合成」速度慢的 5 大底层根因（空镜无限循环解码、CPU 滤镜拖垮 GPU、多路 ffprobe 进程阻塞、前端串行 HTTP 请求、大文件磁盘复制阻塞），使合成吞吐与速度获得本质级提升。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 空镜 (B-roll) 管线轻量化与按需接入 (Priority: P1)

用户在剪辑台上添加或调整了 3~5 个画中画空镜分镜，并点击「重新合成」。系统不再为每个空镜启动 `-stream_loop -1 -i` 并在全片 30 秒内进行多层全屏 Alpha 叠加，也不再对每个空镜素材启动独立的 `ffprobe` 子进程；而是精准按需截取空镜片段，从内存元数据缓存复用 HDR 规格，极速完成空镜画面平替。

**Why this priority**:
这是造成分镜合成卡顿的核心元凶之一。原先每个空镜无论多长都开启无限循环解码并在 FilterGraph 中全时段混合，严重消耗解码器与内存带宽，直接拖慢整体帧率。

**Independent Test**:
在一个 30 秒口播工程中添加 3 个 B-roll 空镜分镜：
- 观察生成的 FFmpeg 命令参数：不再出现 `-stream_loop -1`，而是精准按需截取（如 `-ss ... -t ...`）；
- 监控后台子进程调用：空镜 HDR 规格直接从素材元数据获取，零多余 `ffprobe` 进程启动；
- 验证合成出的成片在空镜入点出点画面切换精准，画质与帧率丝滑稳定。

**Acceptance Scenarios**:
1. **Given** 工程包含若干 B-roll 空镜，**When** 组装 FFmpeg 渲染管线时，**Then** 空镜输入流采用按需截取（精确 source_start 与 duration）输入，严禁对空镜使用 `-stream_loop -1` 无限循环解码。
2. **Given** 待合成的素材已在素材库完成过初次分析，**When** 合成器检查素材是否为 HDR 视频时，**Then** 优先从 `Material` 对象的元数据或进程内缓存读取 `is_hdr`，严禁在渲染循环中串行重复唤起 `ffprobe` 命令行进程。
3. **Given** 空镜仅在特定时间区间（如 3.0s~6.5s）展示，**When** 组装 filter_complex 时，**Then** 仅在对应切片上做视频源平替或精准区间叠加，避免多层无意义的全屏 Alpha 透明度运算。

---

### User Story 2 - CPU 滤镜体系优化与释放 GPU 硬件编码吞吐 (Priority: P1)

用户使用自然清透或美肤滤镜预设进行视频合成，系统采用高吞吐自适应磨皮调色算法，消除 `smartblur` 纯单核 CPU 逐像素运算瓶颈，使 GPU 硬件编码器（如 NVIDIA NVENC、AMD AMF、Intel QSV）全速运转，编码帧率从 15~30 fps 跃升至 120~200+ fps。

**Why this priority**:
视频剪辑的最终编码是显卡强项，但 CPU 滤镜拖累使得硬件编码器长期处于饥饿等待状态。优化滤镜流水线是成倍释放 GPU 性能的核心关键。

**Independent Test**:
在一台具备 GPU 硬件加速的 Windows 机器上，对一个 25 秒高清口播工程执行带滤镜全量渲染：
- 监控渲染过程中 FFmpeg 的编码帧率：稳定在 100+ fps 以上（或实时倍速 3.5x~6.0x 以上）；
- 对比画质：人物面部自然柔滑，无过度虚化或色阶断层，色彩调性与既定预设完全吻合；
- 全片合成耗时压缩至 6~10 秒以内。

**Acceptance Scenarios**:
1. **Given** 用户开启人像调色滤镜（如 `clean_natural`），**When** 构建视频滤镜链时，**Then** 采用高吞吐平滑滤镜方案，彻底淘汰单核高算力开销的 `smartblur` 逐像素高斯递归判定，将 CPU 单帧处理耗时降至 2ms 以内。
2. **Given** 视频缩放与色彩空间转换，**When** libswscale 处理时，**Then** 全链路统一执行 `flags=bicubic+accurate_rnd`，消除计算最沉重的 `lanczos` 带来的 CPU 空耗。
3. **Given** 存在粗剪切片，**When** 组装 FilterGraph 时，**Then** 优化切片与音轨拼接流，防范因过长滤镜字符串导致多线程调度阻塞。

---

### User Story 3 - 前端交互防抖与落盘 I/O 全链路零阻塞 (Priority: P2)

用户在前端界面点击「重新合成」时，界面响应敏捷，前端状态保存与后端落盘之间毫秒级流转；后端成片导出时采用系统级硬链接秒级映射，消除几百 MB 视频在磁盘上的冗余复制。

**Why this priority**:
消灭交互和 I/O 链路的隐形等待，给用户带来即点即跑、合成完成立即播放的畅快体验。

**Independent Test**:
在前端剪辑台连续修改字幕和策略后点击「重新合成」：
- 前端网络监控：不再串行依次等待 3 次 HTTP，而是利用 `Promise.all` 并行提交或直接在 render 请求中原子同步；
- 后端磁盘监控：任务目录成片向 outputs 目录同步时，耗时 < 10ms（通过 hardlink 实现，磁盘空间不额外增加）。

**Acceptance Scenarios**:
1. **Given** 前端点击「重新合成」，**When** 执行保存并合成逻辑时，**Then** 前置的 `updateProjectSubtitles` 与 `updateProjectStrategy` 采用并行异步触发，网络交互时间缩短 60% 以上。
2. **Given** 后端合成出高清成片，**When** 将任务目录下的临时文件同步为输出文件 `output_video_path` 时，**Then** 在同一驱动器卷（Volume）下优先采用 `os.link`（硬链接）瞬时完成落盘，发生跨卷异常时才安全回退至复制。
3. **Given** 重新合成成功后，**When** 前端接收到新成片 URL 时，**Then** 播放器平滑切换视频源，保留当前播放位置或精准定位首帧，无白屏闪烁。

---

## Technical Constraints & Boundaries

1. **真实执行铁律 (Anti-Mock Rule)**：严禁使用伪造时长或直接复制素材来假装提速，所有优化必须作用于真实 FFmpeg 管道并产出有效视频。
2. **画质与音画同步底线**：滤镜提速不得造成画面马赛克、色彩失真或字幕模糊；B-roll 空镜与口播主音轨必须严格保持毫秒级对齐（15ms afade 防爆音）。
3. **全平台兼容性**：GPU 硬件加速不可用时，CPU 回退链路（`libx264`）同样享受滤镜提速收益，无显卡环境下依然流畅运行。

---

## Success Criteria *(mandatory)*

- **SC-001**: 含有 3 个空镜的 30 秒工程，重新合成总耗时在有 GPU 加速环境下缩短至 10 秒以内，在 CPU 环境下缩短至 18 秒以内（综合提速 50%+）。
- **SC-002**: 空镜不再使用 `-stream_loop -1`，且素材规格检测零新增 `ffprobe` 子进程。
- **SC-003**: 前端前置保存与后端文件落盘 I/O 延迟合计降低至 100ms 以内。
- **SC-004**: 全量回归测试（315+ 用例）100% 通过，无音视频不同步或滤镜失效回归。
