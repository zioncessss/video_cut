# 技术研究与选型报告 (Research & Decisions)

**Feature**: `001-driving-school-video-cut`  
**Date**: 2026-09-15  
**Status**: Completed  

---

## 1. 桌面客户端与免终端启动方案 (Desktop Wrapper & Zero-Terminal Launch)

### 调研与权衡
- **方案 A (Electron + Vite + Node/Python 双进程)**：生态最成熟，界面视觉上限高，打包为 macOS `.app`/`.dmg` 和 Windows `.exe` 最标准。但运行内存开销略大，前后端打包需要额外管理 Python 环境。
- **方案 B (Python + PyWebView + Vite 前端静态托管)**：纯 Python 技术栈（利用 `pywebview` 调用系统原生 Edge WebView2 / WebKit 渲染 Web 前端），无需额外安装 Node 运行时打包，启动直接走无控制台模式（Windows `pythonw` / PyInstaller `noconsole`），极简轻量，对音视频处理核心最为友好。
- **方案 C (Tauri + Rust + Vite)**：体积极小，但依赖 Rust 工具链，与本地 Python AI 生态（Whisper、Torch）交互需较多 FFI 或 IPC 通信成本。

### 决策 (Decision)
- **采用方案 B + 方案 A 兼容路线（架构优先采用轻量前后端分离）**：
  - **应用表现层**：采用现代 Web 技术栈（Vite + React + Tailwind CSS），构建出优雅轻快的浅色调 C 端界面。
  - **桌面外壳**：采用 `pywebview` / 轻量桌面窗体加载本地前端，配合启动引导器（Windows `.bat`/`.vbs`/`.exe` 静默快捷方式，macOS `.command`/`.app` 封装），完全规避黑框终端启动。
- **选型理由 (Rationale)**：保持单一主导语言（Python）处理音视频和 AI 接口，避免跨技术栈调用的臃肿，符合宪章“极简高效、防无用循环”准则。

---

## 2. 音频识别 (ASR) 与 LLM 语义校偏技术选型

### 调研与权衡
- **ASR 引擎**：
  - `faster-whisper`：基于 CTranslate2，相比原生 OpenAI Whisper 速度提升 4x，显存降低，支持纯 CPU 快速推理（Int8 量化），支持逐字/逐词/逐句高精度时间戳。
  - 备用：统一兼容 OpenAI 兼容的云端 Audio Transcription API（适用于低配轻量机器）。
- **LLM 语义纠错引擎**：
  - 基于统一的 OpenAI 规范协议客户端（支持 DeepSeek-V3/R1、Qwen、Ollama 本地大模型、OpenAI 等）。
  - Prompt 设计：结构化 Few-Shot 提示词，专为驾校场景定制（包含“科目一/二/三/四”、“倒车入库”、“侧方停车”、“坡道定点”、“打灯”、“学费”、“体检”等特定词表）。
  - 输入：带有时间区间（Start, End）的原始字幕数组。
  - 输出：严格对齐时间区间的修正后字幕数组（禁止篡改时间戳，只修合同音错字与断句）。

### 决策 (Decision)
- ASR 采用 `faster-whisper`（本地首选，自动探测 GPU/CPU）+ 云端 API 优雅降级。
- LLM 纠错采用结构化 JSON 提示词协议，通过适配器解耦大模型厂商。

---

## 3. 音视频复合处理 (J/L-Cut 声画分离) 与 FFmpeg 管道架构

### 核心机制
- **口播原声持续**：主音频流始终以口播音轨为主轨（保持原声抑扬顿挫与讲话连贯性，可配合静音阈值修剪）。
- **画面智能平替（B-roll Overlay）**：
  - 当口播字幕时间段匹配到关键词（例如：`00:04.500 - 00:08.200` 命中“训练场地”）。
  - 系统从对应目录（`storage/materials/venue/`）中筛选/随机选取切片素材。
  - 通过 FFmpeg `filter_complex` 拼接画面：口播画面在命中区间被精确替换为 B-roll 画面，其余区间恢复口播画面。
  - 分辨率与比例统一归一化：通过 `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920` 统一竖屏 9:16（或配置横屏 16:9）。
- **字幕烧录与动态样式**：
  - 生成规范 `.ass` / `.srt` 字幕文件，采用现代加粗无衬线字体，支持高亮关键词样式，通过 `subtitles=...` 滤镜一并压制或作为单独轨。

---

## 4. 硬件资源自适应感知与并发控制 (Hardware-Aware Concurrency)

### 机制设计
- 利用 `psutil` 在任务调度器前探测：
  - 逻辑 CPU 核心数 (`os.cpu_count()`)。
  - 当前系统可用物理内存（Available RAM）。
  - GPU 硬件编码器探测（Windows 优先检测 `h264_nvenc` / `h264_qsv`，Mac 优先检测 `h264_videotoolbox`，未检测到时降级为 `libx264`）。
- **并发槽位计算公式**：
  $$\text{MaxWorkers} = \max(1, \min(\lfloor \text{CPU Cores} / 2 \rfloor, \lfloor \text{Available RAM (GB)} / 2.5 \rfloor))$$
- 采用 `asyncio.Semaphore` 与事件队列驱动，任务状态实时推送到 Web 界面，防止 OOM 崩溃。

---

## 5. Harness 抽象层体系架构 (Harness Abstraction)

### 接口设计
定义统一抽象基类 `BaseHarnessAdapter`：
```python
class BaseHarnessAdapter(ABC):
    @abstractmethod
    async def process_video(self, task_config: TaskConfig) -> GenerationResult:
        """执行剪辑与合成作业"""
        pass

    @abstractmethod
    async def get_resource_metrics(self) -> ResourceMetrics:
        """获取资源利用率"""
        pass

    @abstractmethod
    def get_adapter_info(self) -> dict:
        """返回当前 Harness 元信息（Codex, ZCode, Local 等）"""
        pass
```
- **LocalHarnessAdapter**：内置的 FFmpeg + Faster-Whisper + LLM 管道。
- **CodexHarnessAdapter** / **ZCodeHarnessAdapter**：代理转接到外部 Harness，保持统一数据报文。
