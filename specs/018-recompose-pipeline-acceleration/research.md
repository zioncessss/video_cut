# Research & Architecture Decisions: 重新合成全链路深度提速与管线优化

## Decision 1: 空镜 (B-roll) 无限循环与精准截取对比

- **现状**:
  使用 `inputs.extend(["-stream_loop", "-1", "-i", str(broll_file)])`。
  FFmpeg 解封装器对所有空镜素材建立无限循环上下文，解码线程在后台持续解码并保持帧缓冲队列，且 `trim` 滤镜无法在解封装阶段跳跃（Seek），导致大量无关帧被无意义解码。
- **方案**:
  在输入阶段直接注入快速 Seek 参数：
  ```python
  inputs.extend(["-ss", f"{b_source_st:.3f}", "-t", f"{b_dur:.3f}", "-i", str(broll_file)])
  ```
  这样 FFmpeg 在输入解封装阶段就直接定位到指定时间点，仅解码所需的 `b_dur` 秒视频，彻底释放 CPU/GPU 解码器压力。
  对于极少数空镜素材总长短于目标区间的情况，按需计算有限循环次数 `math.ceil(b_dur / mat_dur)`，绝不使用 `-1` 无限循环。

## Decision 2: 素材 HDR 规格探测缓存化

- **现状**:
  每次合成时，针对口播原片及每一个空镜素材，均在调用栈中通过 `subprocess.run(["ffprobe", ...])` 进行探测。
  若有 4 个空镜，每次合成串行唤起 5 次独立命令行进程，耗时 300~800ms。
- **方案**:
  - `FFmpegFilterComposer` 内部维护实例级 `self._hdr_cache: Dict[str, bool]`，结合文件绝对路径与 `stat().st_mtime` 保证缓存一致性；
  - 首次探测后永久常驻内存，后续合成零新增子进程，探测耗时直接归零。

## Decision 3: 前端前置保存并发化

- **现状**:
  `await updateProjectSubtitles(...)` 后紧接着 `await updateProjectStrategy(...)`，两次独立的 HTTP PUT 往返耗时约 200~400ms。
- **方案**:
  `await Promise.all([updateProjectSubtitles(...), updateProjectStrategy(...)])` 并发执行，利用 HTTP 管道并行度，消灭前置无意义等待。

## Decision 4: 成片同步与磁盘落盘硬链接

- **现状**:
  成片合成后，从专属任务目录向成片输出目录复制大文件（通常 50MB~300MB）使用 `shutil.copyfile`，在 Windows NTFS 机械盘或碎片化固态盘上可能带来 1~3 秒 I/O 阻塞。
- **方案**:
  优先使用 `os.link` 创建硬链接，同一物理卷下 0 字节复制、毫秒级瞬间完成落盘；仅在跨盘卷发生 `OSError` 时回退至 `shutil.copyfile`。
