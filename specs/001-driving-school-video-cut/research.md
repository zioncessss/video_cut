# 技术研究与混合驱动架构调研报告 (Research & Architecture)

**Feature**: `001-driving-school-video-cut`  
**Date**: 2026-09-15  
**Status**: Completed (Updated for Hybrid Dual-Engine Architecture)  

---

## 1. 核心架构决策：混合双引擎驱动 (Hybrid Architecture)

根据用户明确决策：**“固定的操作用硬编码，高阶操作灵活操作用套壳”**。

```
┌─────────────────────────────────────────────────────────────┐
│                    C端 浅色调 Web / 桌面 UI                  │
│       (素材管理 / 双栏播放器 / 时间轴字幕卡片 / 底部AI指令框)    │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
        【固定操作：硬编码】              【高阶操作：Harness套壳】
               ▼                               ▼
┌─────────────────────────────┐ ┌─────────────────────────────┐
│    Native Engine (本地内核)   │ │  Harness Wrapper (智能体壳) │
│  - 素材目录归档与元数据读取   │ │  - 语义理解与LLM专有词纠错 │
│  - 纯Python/FFmpeg硬件直驱   │ │  - 复杂自然语言微调指令编译 │
│  - 确定性音视频J/L-Cut复合渲染│ │  - 智能镜头混剪剧本生成     │
│  - psutil硬件资源动态侦测    │ │  - Codex / ZCode 进程适配器 │
│  - WebSocket 毫秒级进度回传  │ │  - 提示词上下文与会话管理   │
└─────────────────────────────┘ └─────────────────────────────┘
```

### 1.1 职责边界划分矩阵 (Responsibility Matrix)

| 功能场景 | 驱动引擎 | 实现方式 | 选型与优势 |
| :--- | :--- | :--- | :--- |
| **素材上传与目录落盘** | **硬编码 (Native)** | Python 文件系统 API | 毫秒级存储，直接写入 `storage/materials/{category}/`，无需 Agent 介入 |
| **视频元数据提取** | **硬编码 (Native)** | `ffprobe` / `cv2` | 精准获取视频长宽、帧率、时长，确定性高 |
| **基础音视频复合渲染 (J/L-Cut)** | **硬编码 (Native)** | 结构化组装 FFmpeg 滤镜 | 参数已知，直接调 FFmpeg 原生渲染，耗时最短、无 Token 消耗、零不确定性 |
| **硬件监控与并发节流** | **硬编码 (Native)** | `psutil` + 信号量 | 实时采集 CPU/内存/GPU，精确控制并发槽位 |
| **语音字幕转文字 (ASR)** | **硬编码 (Native)** | `faster-whisper` | 本地 CTranslate2 库直跑，快速产出毫秒级原始时间戳 |
| **驾校术语上下文纠偏** | **Harness 套壳** | Codex / ZCode / LLM | 基于驾校特定词库与上下句语义，推理并纠正同音错别字 |
| **底部自然语言微调** | **Harness 套壳** | Codex / ZCode / Agent | 用户输入“把第3句空镜换成另一个场地素材”、“将节奏调快20%”，由 Harness 解析意图并重写剪辑配置 |
| **多样化批量脚本生成** | **Harness 套壳** | Codex / ZCode | 根据推广目标（地点/价格/教练优势），生成不同维度的空镜编排逻辑 |

---

## 2. Harness 进程通信与套壳调研 (Harness Integration Research)

### 2.1 Codex / ZCode 的对接模式
针对本地运行的 Codex、ZCode 等智能体 Harness，调研了以下三种通信模式：

1. **子进程标准流交互 (CLI Subprocess stdio)**：
   - 后端通过 `asyncio.create_subprocess_exec` 托管 Harness 命令行生命周期。
   - 通过标准输入（`stdin`）下发 JSON-RPC 或 Prompt 指令，监听标准输出（`stdout`）解析生成结果。
   - **适用**：独立 CLI 格式的 Codex/ZCode 引擎，环境隔离性好。
2. **轻量本地服务转发 (Local HTTP / WebSocket Proxy)**：
   - 若 Codex / ZCode 以 Background Server / API Daemon 形式运行，后端通过统一封装的 `HarnessClient` 进行 HTTP/WS 调用。
   - **适用**：常驻型 Harness 服务，响应延迟低。
3. **本地内置模拟 Harness (Local Fallback Harness)**：
   - 当用户本地尚未安装或未配置 Codex/ZCode 时，系统内置一套基于 OpenAI 兼容协议的轻量 Agent Runner，保证开箱即用。

### 2.2 调研结论
- 采用 **适配器模式（Adapter Pattern）**：统一暴露 `HarnessBridge` 接口。
- 支持两套执行器：
  - `CliHarnessAdapter`：面向标准 Codex / ZCode 命令行工具。
  - `EmbeddedHarnessAdapter`：内置轻量 LLM Agent，无需前置安装复杂环境即可完整体验所有高级操作。

---

## 3. 免终端桌面启动调研 (Zero-Terminal Desktop Launch)

- **Windows 方案**：
  - 编写静默引导脚本 `launcher.vbs`，内部调用 `pythonw launcher.py`。
  - `launcher.py` 启动轻量 FastAPI 守护进程，并唤起 `pywebview`（基于系统内置 Edge WebView2），无 CMD 黑框，开箱即是原生 Windows 桌面窗口。
- **macOS 方案**：
  - 打包为 `.app` 或静默 `.command` 脚本，唤起 Cocoa WebKit 窗口，自动入驻 Dock 栏。
