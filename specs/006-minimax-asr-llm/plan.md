# Implementation Plan: MiniMax 统一接管 ASR 与大模型智能剪辑 (006-minimax-asr-llm)

**Branch**: `006-minimax-asr-llm` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-minimax-asr-llm/spec.md`

## Summary

本特性旨在用 MiniMax 云端 API 统一替换原有的高耗时本地 CPU Whisper ASR 与第三方 LLM 混合方案。
通过调用 MiniMax 极速 ASR 接口（`asr-1.0` + `verbose_json` + `timestamp_level="word"`）实现毫秒级字时间戳秒级转写，彻底消除 100% CPU 占用与卡顿；同时统一采用 `MiniMax-Text-01` 承担 Tier A（字幕纠偏）与 Tier B（分镜决策），以不足 0.06 元/条的极低成本实现高质量短视频全自动混剪闭环，并具备本地 Faster-Whisper 离线自动降级容灾能力。

---

## Technical Context

**Language/Version**: Python 3.11.15 (FastAPI 后端), TypeScript 5.2 + React 18.2 (Vite 前端)

**Primary Dependencies**: `httpx` (HTTP 通信), `faster-whisper` (本地离线兜底), `ffmpeg` (音频提取与合成), `pydantic` v2

**Storage**: SQLite (`storage/videocut.db`), 本地配置 (`storage/settings.json`), 词库 (`storage/glossary.json`)

**Testing**: `pytest` (后端单元测试与集成测试), `pnpm build` (前端构建编译)

**Target Platform**: Windows 10/11 & macOS (Desktop Electron 应用 + 本地 Python 引擎)

**Project Type**: 桌面端 AI 驱动短视频全自动混剪系统

**Performance Goals**: 60s 口播视频 ASR 转写耗时从 30~70s 降低至 2~5s，全链路 API 成本控制在 0.08 元/条以内

**Constraints**: 断网或服务抖动时 100% 自动降级本地 faster-whisper；API Key 绝对零明文外露；严禁测试 Mock 混入真实业务

**Scale/Scope**: 支持批量 10~50 视频快速转写与混剪，单并发 ASR 耗时 <5s

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. C端体验与免终端启动**: 全流程状态与错误信息均在前端弹窗与进度条呈现，连通性测试一键可视化，零命令行依赖。
- [x] **II. Harness 抽象与引擎解耦**: MiniMax 作为 `api` harness 的标准 OpenAI 兼容模型，ASR 统一在 `asr_runner.py` 内部做适配器封装，对外暴露契约保持完全不变。
- [x] **III. 智能音视频管线与声画解耦**: 严格继承既有口播保留 + J/L Cut 替换，字级时间戳直接注入 6~12 字黄金视读意群切分。
- [x] **IV. 硬件感知与批处理并发调度**: ASR 移至云端后极大卸载本地 CPU 负载，释放计算资源给 FFmpeg 本地高效视频压制。
- [x] **V. 极简高效与防无用循环**: 共享同一组 MiniMax Key，单接口轻量请求，无需轮询死循环，直接返回结果。

---

## Project Structure

### Documentation (this feature)

```text
specs/006-minimax-asr-llm/
├── plan.md              # 本实施计划
├── research.md          # Phase 0 调研与技术决策 (接口参数、字级时间戳、降级方案)
├── data-model.md        # Phase 1 数据模型映射 (MiniMaxWordItem -> SubtitleWord)
├── quickstart.md        # Phase 1 自动化与手动走查验证指南
├── contracts/           # Phase 1 接口契约
│   └── api.md           # MiniMax STT、Chat Completion 与 Settings API 契约
└── checklists/
    └── requirements.md  # 需求质量检查清单 (已全绿)
```

### Source Code Layout

```text
backend/
├── app/
│   ├── api/
│   │   ├── editor.py            # 主剪辑流水线 (无需大动，沿用 ASRRunner)
│   │   └── settings.py          # 新增 ASR Provider 设置与连通性检测接口
│   ├── core/
│   │   └── config.py            # 读取 settings.json 中的 minimax/asr 配置
│   ├── harness_bridge/
│   │   ├── api_engine.py        # 沿用 OpenAI 协议直连 MiniMax-Text-01
│   │   └── prompting.py         # 沿用 Tier A 纠偏与 Tier B 分镜提示词
│   └── native_engine/
│       └── asr_runner.py        # 新增 transcribe_minimax 与自动降级 local-whisper 逻辑
tests/
├── test_minimax_asr.py          # [NEW] MiniMax ASR 单元测试、时间戳映射与降级测试
├── test_all_flows.py            # 端到端全链路回归验证
└── test_settings_api.py         # 设置接口与掩码安全验证
frontend/
└── src/
    ├── pages/
    │   └── Settings.tsx         # 设置页 UI：MiniMax 提供商、ASR 切换与连通性检测
    └── services/
        └── api.ts               # 前端 API 调用封装 (testConnection 等)
```

---

## Complexity Tracking

| 模块 / 决策 | 为何需要 | 拒绝更简单替代方案的原因 |
| :--- | :--- | :--- |
| **双层 ASR 执行器 (云端优先+本地降级)** | 保证断网或 API 异常时应用仍然可用 | 纯云端无兜底会在断网或欠费时导致应用直接不可用；纯本地则速度极慢无法解决根本痛点 |
| **字级时间戳映射器** | 将 MiniMax `segments` 转换为系统统一 `words` | 若直接截断 MiniMax 句子会导致字幕长度不可控（过长或过碎），无法满足短视频视读标准 |