# Implementation Plan: 驾校短视频网感剪辑工作台 (C-End Harness Video Cut Workbench)

**Branch**: `master` | **Date**: 2026-09-15 | **Spec**: [specs/001-driving-school-video-cut/spec.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/spec.md)

**Input**: Feature specification from `specs/001-driving-school-video-cut/spec.md`

---

## Summary

本项目为 Codex / ZCode / 本地自定义 Harness 封装面向 C 端驾校推广业务的桌面剪辑套件。采用“桌面轻量窗体（免终端启动） + 浅色调响应式 Web 工作台 + Python 智能音视频管线（FFmpeg + Faster-Whisper + LLM 语义校错） + 硬件自适应并发池”架构，实现口播原声持续、语义关键词智能平替空镜（J/L-Cut）、双轨字幕可视化微调以及防死机批量混剪。

---

## Technical Context

**Language/Version**: Python 3.11+ (后端与音视频管线) / TypeScript + React 18+ (Web 前端)  
**Primary Dependencies**: 
- 后端：`fastapi`, `uvicorn`, `faster-whisper`, `ffmpeg-python`, `psutil`, `pydantic`, `pywebview`
- 前端：`vite`, `react`, `lucide-react`, `tailwindcss`, `axios`
- 系统工具：`ffmpeg`, `ffprobe`  
**Storage**: 本地文件系统目录隔离存储（`storage/materials/{category}/`） + SQLite / JSON 本地工程持久化  
**Testing**: `pytest` (后端单元与管线集成测试) + `vitest` (前端组件与状态测试)  
**Target Platform**: Windows 10/11 64位 & macOS 12+ (双端免终端桌面启动)  
**Project Type**: 桌面封装 Web 混合应用 (Desktop C-End App)  
**Performance Goals**: 
- 单段 60 秒口播视频 ASR 与 LLM 纠偏处理时间 < 8 秒（GPU）或 < 20 秒（CPU）
- 本地 1080p 视频渲染速度达到 1.5x~3x 实时速度（启用硬件加速时）
- 批量处理时内存安全水位维持在 75% 以下，杜绝 OOM 崩溃  
**Constraints**: 
- 启动完全脱离控制台黑框终端
- 界面风格必须为浅色现代高质感 UI（Light Mode）
- 音视频合成必须严格保留口播原声连贯性  
**Scale/Scope**: 单机支持 100+ 视频素材管理，单次支持 50+ 视频批量混剪调度  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章准则 | 评估结果 | 落实机制 |
| :--- | :--- | :--- |
| **I. C端体验与免终端启动** | ✅ 通过 | 封装独立桌面启动入口（`pythonw` + `pywebview` / 静态打包），无终端依赖 |
| **II. Harness 抽象与引擎解耦** | ✅ 通过 | 设计 `BaseHarnessAdapter` 统一接口契约，适配 Codex/ZCode/Local |
| **III. 智能音视频管线与声画解耦** | ✅ 通过 | ASR (Faster-Whisper) + LLM 语义纠错 + FFmpeg 复合滤镜 J/L-Cut |
| **IV. 硬件感知与并发调度** | ✅ 通过 | `psutil` 动态算力测算公式，自适应并发限制，预防 OOM |
| **V. 极简高效与防无用循环** | ✅ 通过 | 扁平结构，无冗余多层抽象，事件驱动，释放句柄与进程 |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-driving-school-video-cut/
├── spec.md              # 业务需求与用户故事规格书
├── plan.md              # 本技术实现架构方案
├── research.md          # 选型调研与架构决策报告
├── data-model.md        # 核心数据实体与状态模型
├── quickstart.md        # 快速启动与测试验证指南
├── contracts/           # 接口协议与契约
│   ├── harness-adapter.md # Harness 抽象契约
│   └── web-api.md         # 前后端交互 API 协议
└── tasks.md             # 任务清单 (由 $speckit-tasks 生成)
```

### Source Code (repository root)

```text
video_cut/
├── launcher.py               # 桌面应用免终端启动入口 (PyWebView / 桌面窗体)
├── start_windows.vbs         # Windows 静默双击启动引导脚本
├── start_mac.command         # macOS 双击启动引导脚本
├── backend/                  # 后端服务与音视频引擎
│   ├── app/
│   │   ├── api/              # REST & WebSocket 路由
│   │   │   ├── materials.py  # 素材上传与目录管理
│   │   │   ├── editor.py     # 剪辑解析、字幕微调、即时渲染
│   │   │   ├── batch.py      # 批量混剪调度
│   │   │   └── system.py     # 硬件资源监测
│   │   ├── core/             # 核心配置与资源自适应调度器
│   │   │   ├── config.py
│   │   │   └── resource.py   # CPU/内存/GPU 检测与并发配额
│   │   ├── harness/          # Harness 抽象层
│   │   │   ├── base.py       # BaseHarnessAdapter 抽象基类
│   │   │   ├── local.py      # 本地内置音视频剪辑 Harness
│   │   │   └── codex.py      # Codex / ZCode 适配器实现
│   │   ├── pipeline/         # 音视频处理流水线
│   │   │   ├── asr.py        # Faster-Whisper 提取时间戳
│   │   │   ├── llm.py        # 驾校专有术语语义纠偏
│   │   │   └── composer.py   # FFmpeg J/L-Cut 多轨滤镜合成器
│   │   └── main.py           # FastAPI 服务主入口
│   └── requirements.txt      # 后端依赖配置
├── frontend/                 # 浅色质感 C 端前端工程
│   ├── src/
│   │   ├── components/       # 公共组件 (播放器、波形条、时间轴卡片)
│   │   ├── pages/            # 页面路由
│   │   │   ├── AssetLibrary.tsx  # 素材库四分类管理
│   │   │   ├── VideoEditor.tsx   # 剪辑工作台 (左播放器右字幕底指令)
│   │   │   ├── BatchCut.tsx      # 批量混剪生产
│   │   │   └── Settings.tsx      # Harness 与参数设置
│   │   ├── services/         # API 请求与 WebSocket 客户端
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── storage/                  # 素材与渲染产物本地持久化目录
│   └── materials/
│       ├── talking_head/     # 口播视频
│       ├── venue/            # 场地视频
│       ├── medical/          # 体检视频
│       └── lesson/           # 教学学车视频
└── tests/                    # 自动化测试套件
    ├── test_asr_llm.py       # ASR 与 LLM 纠错测试
    ├── test_composer.py      # FFmpeg 声画分离 J/L-Cut 渲染测试
    └── test_resource.py      # 硬件感知调度测试
```

---

## 计划执行阶段说明

1. **Phase 0 (调研决策)**：已输出 [research.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/research.md)
2. **Phase 1 (架构设计与契约)**：
   - 数据实体：[data-model.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/data-model.md)
   - 接口协议：[contracts/harness-adapter.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/contracts/harness-adapter.md)、[contracts/web-api.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/contracts/web-api.md)
   - 验证指南：[quickstart.md](file:///d:/project/video_cut/specs/001-driving-school-video-cut/quickstart.md)
3. **Phase 2 (任务拆解)**：即将通过 `$speckit-tasks` 自动拆解生成 `tasks.md`，随后进行落地开发。
