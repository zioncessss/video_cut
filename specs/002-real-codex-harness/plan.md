# Implementation Plan: 真实 Codex Harness 驱动的智能纠错与自然语言剪辑工作台 (Real Codex Harness Video Cut Bridge)

**Branch**: `002-real-codex-harness` | **Date**: 2026-09-16 | **Spec**: [specs/002-real-codex-harness/spec.md](spec.md)

**Input**: Feature specification from `specs/002-real-codex-harness/spec.md`

## Summary

将视频剪辑工作台中的外部智能体桥接器全面做真：淘汰原占位与模拟降级，正式通过非交互式 `codex exec` 子进程驱动用户本机的 Codex CLI，实现驾校口播字幕的高精度大模型语义纠偏、全能自然语言微调（文案润色、B-roll 空镜再分配、时间轴节奏伸缩）、设置中心持久化以及前端实时引擎状态感知与平滑降级。

## Technical Context

**Language/Version**: Python 3.11+ (Backend), TypeScript / React 18+ (Frontend)  
**Primary Dependencies**: FastAPI, Pydantic v2, Vite, TailwindCSS, Lucide-React, Codex CLI v0.150.1+  
**Storage**: 本地文件持久化 (`storage/settings.json`, `storage/materials/`, `storage/materials_meta.json`)  
**Testing**: pytest, pytest-asyncio, Playwright E2E  
**Target Platform**: Windows 11 (PowerShell/CMD, 兼容 macOS)  
**Project Type**: Web 桌面工作台 (C-End Harness 套壳工具)  
**Performance Goals**: 单次 Codex CLI 纠错/微调响应时间 2.5 ~ 6 秒；前端连通性检测 < 3 秒  
**Constraints**: 
- Windows 环境下必须显式断开子进程 stdin 管道 (`stdin=asyncio.subprocess.DEVNULL`) 防范永久挂起。
- 采用 `--sandbox read-only --ephemeral -o <temp_file>` 参数避免 ANSI 转义污染与脏会话遗留。
- 35 秒超时阈值保护，超时或异常自动降级至内置规则引擎 `EmbeddedHarnessBridge`。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. C端体验与免终端启动**: Codex CLI 调用以无头子进程在后台静默运行，无需用户打开命令行黑框，所有反馈在 Web UI 中展现。
- [x] **II. Harness 抽象与引擎解耦**: 继承并实现 `BaseHarnessBridge`，通过 `CodexHarnessBridge` 封装所有 Codex CLI 专属调度，与前端 Web API 解耦。
- [x] **III. 智能音视频管线与声画解耦**: 专注于 ASR 字幕大模型纠偏与基于素材元数据的空镜微调，支持多轮交互微调。
- [x] **IV. 极简高效与防无用循环**: 采用短链路直接执行与临时文件消息提取，无过度深层抽象或嵌套轮询。
- [x] **V. UI/UX 风格规范**: 遵循 Clean Light Mode，增加连通性检测按钮、引擎状态徽标及高亮对比卡片。

## Project Structure

### Documentation (this feature)

```text
specs/002-real-codex-harness/
├── plan.md              # 本实现计划
├── research.md          # Phase 0 调研结果
├── data-model.md        # Phase 1 数据模型
├── quickstart.md        # Phase 1 快速验证指南
├── contracts/           # Phase 1 接口契约
│   └── api-endpoints.md # Web 与 Harness 接口协议
└── tasks.md             # Phase 2 任务清单 (由 speckit-tasks 生成)
```

### Source Code Impact

```text
backend/
├── app/
│   ├── api/
│   │   ├── editor.py           # 增强：纠错接口返回详细变动明细与高亮
│   │   ├── instruction.py      # 增强：支持全能微调意图（文案/空镜/时间）
│   │   └── settings.py         # 新增：POST /test-harness 探针与持久化更新
│   ├── core/
│   │   └── config.py           # 扩展：读取与同步 settings.json 中的模型参数
│   └── harness_bridge/
│       ├── base.py             # 扩充：HarnessPlanResponse 与纠错结果模型
│       ├── codex.py            # 重构：真正接入 codex exec 子进程调用与超时降级
│       └── factory.py          # 维护：动态解析 active_harness 单例
tests/
└── test_codex_bridge.py        # 新增：Codex 子进程、解析与降级单元测试

frontend/
├── src/
│   ├── pages/
│   │   ├── Settings.tsx        # 增强：增加「测试连通性」按钮、延迟反馈与模型覆盖输入
│   │   └── VideoEditor.tsx     # 增强：增加驱动引擎状态徽章、纠错高亮卡片与微调联动
│   └── services/
│       └── api.ts              # 扩展：封装 testHarness 连接测试请求
```

## Phase 0: Outline & Research
- [x] 验证 `codex exec` 在当前环境运行状态与模型配置 (`glm-5.3-flash` on `127.0.0.1:15721`)
- [x] 验证 Windows 管道防挂起参数及 `-o <temp_file>` 结构化输出提取
- [x] 产出 `specs/002-real-codex-harness/research.md`

## Phase 1: Design & Contracts
- [x] 定义 `data-model.md`（Settings、CorrectionResult、NaturalInstruction）
- [x] 定义 `contracts/api-endpoints.md`（探针接口、纠错接口、微调接口）
- [x] 编写 `quickstart.md` 提供自动化与端到端验证指导
- [x] 更新 `AGENTS.md` 上下文指向本 plan.md