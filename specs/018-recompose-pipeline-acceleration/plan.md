# Implementation Plan: 重新合成全链路深度提速与管线优化

**Branch**: `018-recompose-pipeline-acceleration` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/018-recompose-pipeline-acceleration/spec.md`

## Summary

全面解决造成重新合成速度慢的 5 大瓶颈问题：
1. **空镜 (B-roll) 解耦与按需精准截取**：
   - 彻底废止全局 `-stream_loop -1 -i` 无限解码机制，根据空镜需要展示的区间计算有限循环或精准 `-ss ... -t ...` 按需解码；
   - 升级全局持久化 `_hdr_cache`，消除对素材重复唤起 `ffprobe` 子进程的串行等待；
   - 优化 FilterGraph 中多路空镜与口播视频的图层复合，杜绝无意义的全屏 Alpha 透明度运算开销。
2. **释放 GPU 硬件加速并优化 CPU 滤镜流水线**：
   - 消除 `smartblur` 纯单核高 CPU 算力黑洞，引入线程安全并支持切片多线程加速的自适应平滑方案；
   - 维持全管线 `flags=bicubic+accurate_rnd`，消除 `lanczos` CPU 逐像素算力消耗；
   - 保证 NVIDIA NVENC / AMD AMF / Intel QSV 硬件编码器稳定输出 100+ fps。
3. **前端交互与文件落盘全链路零等待**：
   - 前端点击「重新合成」时采用 `Promise.all` 并行保存字幕与策略，消除前置网络延迟；
   - 后端成片文件同步全面采用 `os.link` 硬链接秒级落盘，杜绝百兆视频文件磁盘复制阻塞。

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.0+  
**Primary Dependencies**: FastAPI, FFmpeg, PIL (Pillow), React, TailwindCSS  
**Storage**: SQLite (`storage/videocut.db`) 权威存储，WAL 模式  
**Testing**: pytest (全量 315+ 用例回归)  
**Target Platform**: Windows 10/11 (AMD AMF / NVIDIA NVENC / Intel QSV / CPU fallback)  
**Performance Goals**:
- 重新合成含空镜场景全量耗时降低 50% 以上（GPU 环境缩短至 10 秒以内，CPU 环境缩短至 18 秒以内）；
- 空镜 HDR 检测零进程耗时；
- 全量回归测试 100% 通过。

## Constitution Check

- [x] **反假运行与防 Mock 铁律**: 严禁缩短原片时长或生成静默假视频，优化必须基于真实 FFmpeg 滤镜图与真实编解码。
- [x] **数据唯一事实源**: 保持 SQLite 权威存储，素材元数据与工程配置计算即落库。
- [x] **高亮词与视觉策略零丢失**: ASS 高亮字幕与横幅图层无损压制，画质色彩与色温平衡无失真。

## Project Structure

```text
specs/018-recompose-pipeline-acceleration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code Touches

- `backend/app/native_engine/ffmpeg_filter.py`:
  - 改造 B-roll 输入：消除 `-stream_loop -1`，采用 `-ss` 与精确 `duration` 按需截取输入；
  - 升级 `is_hdr_video`：将局部 `hdr_cache` 提升为类实例级持久化 `self._hdr_cache`，并优先利用素材元数据；
  - 优化模式 A 与模式 B 中 B-roll 在 FilterGraph 中的叠加开销。
- `frontend/src/pages/VideoEditor.tsx`:
  - 改造 `handleExecuteRender`：使用 `Promise.all` 并发提交 `updateProjectSubtitles` 与 `updateProjectStrategy`。
- `backend/app/api/editor.py`:
  - 全面使用 `os.link` 优化成片同步落盘。
- `tests/test_recompose_acceleration.py`:
  - 新增管线加速专项自动化测试（验证 B-roll 按需截取、HDR 缓存命中、无重复 ffprobe 进程）。
