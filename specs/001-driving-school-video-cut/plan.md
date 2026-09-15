# Implementation Plan: 驾校短视频网感剪辑工作台 (混合双引擎架构)

**Branch**: `master` | **Date**: 2026-09-15 | **Spec**: [specs/001-driving-school-video-cut/spec.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/spec.md)

**Input**: Feature specification from `specs/001-driving-school-video-cut/spec.md` + 混合架构决策（固定操作硬编码，高阶灵活操作 Harness 套壳）

---

## Summary

本项目为 Codex、ZCode 等智能体 Harness 打造面向 C 端的驾校营销短视频剪辑外壳。
核心采用 **混合双引擎驱动体系（Hybrid Dual-Engine）**：
1. **固化高效执行层 (Native Hardcoded Engine)**：素材目录四分类存储、音视频元数据探测、毫秒级 ASR 提取、确定性 FFmpeg 多轨复合滤镜（J/L-Cut）合成压制、系统硬件资源监控与并发控制。
2. **高阶智能套壳层 (Harness Wrapper Layer)**：通过统一 `HarnessBridge` 接口套壳连接外部 `Codex`、`ZCode`（及内置轻量 Agent 备用），驱动驾校专有词语义纠偏、底部自然语言微调指令理解重写、以及多样化批量混剪脚本规划。
3. **免终端桌面启动 (Zero-Terminal Desktop)**：`pywebview` 桌面原生窗口承载现代化浅色调 Web 工作台，Windows/macOS 双端双击即开。

---

## Technical Context

**Language/Version**: Python 3.11+ (Native 核心与 Harness 桥接) / TypeScript + React 18+ (C 端现代界面)  
**Primary Dependencies**: 
- 固化内核：`fastapi`, `uvicorn`, `faster-whisper`, `ffmpeg-python`, `psutil`, `pydantic`, `pywebview`
- 套壳交互：`asyncio.subprocess` (对接 Codex/ZCode CLI), OpenAI 协议 SDK (对接 LLM/Agent)
- 前端交互：`vite`, `react`, `lucide-react`, `tailwindcss`, `axios`  
**Storage**: 物理目录结构 (`storage/materials/{talking_head,venue,medical,lesson}/`) + 本地工程配置文件  
**Testing**: `pytest` (测试 Native 流水线及 Harness 适配器通信)  
**Target Platform**: Windows 10/11 & macOS 12+ (免终端桌面运行)  
**Project Type**: Desktop Hybrid Web Application (桌面套壳 Web 交互)  

---

## Constitution Check

| 宪章准则 | 评估结果 | 落实机制 |
| :--- | :--- | :--- |
| **I. C端体验与免终端启动** | ✅ 通过 | 封装独立桌面启动入口（`pythonw` + `pywebview`），无命令行暴露 |
| **II. Harness 抽象与套壳解耦** | ✅ 通过 | 固化操作本地快跑，高阶意图由 `HarnessBridge` 套壳调度 Codex / ZCode |
| **III. 智能音视频管线与声画解耦** | ✅ 通过 | 确定性 FFmpeg 滤镜管道保留口播音轨，关键词精准切入空镜 |
| **IV. 硬件感知与并发调度** | ✅ 通过 | `psutil` 算力检测，自适应调节并发限制，防 OOM 死机 |
| **V. 极简高效与防无用循环** | ✅ 通过 | 职责分明：硬编码保证性能与稳定性，Harness 保证智能与灵活，杜绝冗余抽象 |

---

## Project Structure

```text
video_cut/
├── launcher.py               # 桌面应用免终端启动入口 (PyWebView 原生窗口)
├── start_windows.vbs         # Windows 静默双击启动脚本 (无黑框)
├── start_mac.command         # macOS 双击启动脚本
├── backend/
│   ├── app/
│   │   ├── api/              # REST 路由 (Web 前端交互)
│   │   │   ├── materials.py  # [硬编码] 素材上传与四分类存储
│   │   │   ├── editor.py     # [混合] 剪辑解析与视频渲染
│   │   │   ├── instruction.py# [Harness套壳] 底部自然语言微调接口
│   │   │   ├── batch.py      # [混合] 批量生产调度
│   │   │   └── system.py     # [硬编码] 硬件资源监控
│   │   ├── core/             # 系统基础支撑
│   │   │   ├── config.py
│   │   │   └── resource.py   # [硬编码] psutil 算力监控与并发限流
│   │   ├── native_engine/    # 【固化执行层】
│   │   │   ├── asr_runner.py # Faster-Whisper 毫秒级提取
│   │   │   ├── ffmpeg_filter.py # 确定性 J/L-Cut 多轨滤镜压制
│   │   │   └── storage.py    # 目录分类读写与元数据探查
│   │   ├── harness_bridge/   # 【高阶套壳层】
│   │   │   ├── base.py       # BaseHarnessBridge 统一协议
│   │   │   ├── codex.py      # Codex Harness 适配器 (CLI/RPC)
│   │   │   ├── zcode.py      # ZCode Harness 适配器 (CLI/RPC)
│   │   │   └── embedded.py   # 内置轻量 Agent 适配器 (备用回退)
│   │   └── main.py           # FastAPI 服务主入口
│   └── requirements.txt
├── frontend/                 # 浅色质感 C 端前端 (Vite + React + Tailwind CSS)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AssetLibrary.tsx  # 素材库四分类管理
│   │   │   ├── VideoEditor.tsx   # 剪辑工作台 (左播放器右字幕底指令)
│   │   │   ├── BatchCut.tsx      # 批量混剪生产
│   │   │   └── Settings.tsx      # Harness 引擎切换与参数设置
│   │   └── ...
├── storage/                  # 素材物理库
│   └── materials/
│       ├── talking_head/
│       ├── venue/
│       ├── medical/
│       └── lesson/
└── tests/
    ├── test_native_pipeline.py  # 固化渲染测试
    └── test_harness_bridge.py   # Harness 通信与微调测试
```
