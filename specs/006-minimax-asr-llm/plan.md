# Implementation Plan: MiniMax 统一接管 ASR 与大模型智能剪辑 (006-minimax-asr-llm)

**Branch**: `006-minimax-asr-llm` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-minimax-asr-llm/spec.md`

### Summary

本特性旨在用 MiniMax 云端 API 统一替换原有的高耗时本地 CPU Whisper ASR 与第三方 LLM 混合方案，并彻底根治此前出现的 **“成片 0% 分镜切入”** 与 **“字幕中文词组腰斩（千万不/要报）”** 两大核心缺陷：
1. **极速 ASR 与自然意群断句（VideoLingo 范式）**：调用 MiniMax 极速 ASR 接口（`asr-1.0` + `verbose_json` + `timestamp_level="word"`）实现毫秒级字/词时间戳秒级转写；彻底废除 14 字机械硬切，基于词尾标点感知与语法意群边界切分，8~18 字宽松合并完整一句话或半句话，100% 消除中文词腰斩与孤立走马灯碎词；
2. **稀疏剪辑指示清单（Editorial Cue Sheet 契约）**：重构大模型分镜决策契约，大模型仅输出强相关切入区间（`broll_cues`，Token < 300），耗时从 67s 降至 2s，彻底根除输出爆 Token 截断导致的语法破损；
3. **强相关精准匹配 + 自由段落自适应随机铺底**：针对 1~2 分钟短视频，大模型精准锁定场地（venue）、练车（lesson）、体验（experience）强相关场景；其余自由段落由本地编排层自适应随机调度素材铺设 3~5 秒窗口，硬性收敛至 **60%~70%** 黄金成片覆盖率（可在策略中配置）；开场 1.8s 真人、报价手势、结尾 CTA 严格设为禁切红线；
4. **统一凭据与离线容灾**：单 Key 共享供给 ASR 与 LLM，保持本地 Faster-Whisper 与智能节奏槽位填充兜底。

---

## Technical Context

**Language/Version**: Python 3.11.15 (FastAPI 后端), TypeScript 5.2 + React 18.2 (Vite 前端)

**Primary Dependencies**: `httpx` (HTTP 通信), `faster-whisper` (本地离线兜底), `ffmpeg` (音频提取与合成), `pydantic` v2

**Storage**: SQLite (`storage/videocut.db`), 本地配置 (`storage/settings.json`), 词库 (`storage/glossary.json`)

**Testing**: `pytest` (后端单元测试与集成测试), `pnpm build` (前端构建编译)

**Target Platform**: Windows 10/11 & macOS (Desktop Electron 应用 + 本地 Python 引擎)

**Project Type**: 桌面端 AI 驱动短视频全自动混剪系统

**Performance Goals**: 60s 口播视频 ASR 转写耗时 2~5s，分镜决策从 >60s 降至 <3s，成片空镜总时长稳稳达到 60%~70%，全链路 API 成本控制在 0.06 元/条以内

**Constraints**: 断网或服务抖动时 100% 自动降级本地 faster-whisper 与自适应铺底；API Key 绝对零明文外露；严禁测试 Mock 混入真实业务

**Scale/Scope**: 支持批量 10~50 视频快速转写与混剪，单并发 ASR 耗时 <5s

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. C端体验与免终端启动**: 全流程状态与错误信息均在前端弹窗与进度条呈现，连通性测试一键可视化，零命令行依赖。
- [x] **II. Harness 抽象与引擎解耦**: MiniMax 作为 `api` harness 的标准 OpenAI 兼容模型，ASR 统一在 `asr_runner.py` 内部做适配器封装，对外暴露契约保持完全不变。
- [x] **III. 智能音视频管线与声画解耦**: 严格继承既有口播保留 + J/L Cut 替换，字级时间戳直接注入 8~18 字自然意群切分，声画严丝合缝对齐。
- [x] **IV. 硬件感知与批处理并发调度**: ASR 移至云端后极大卸载本地 CPU 负载，释放计算资源给 FFmpeg 本地高效视频压制。
- [x] **V. 极简高效与防无用循环**: 采用稀疏 Cue Sheet 模式，单接口 Token 消耗 <300，彻底消除超时、死循环与截断。

---

## Project Structure

### Documentation (this feature)

```text
specs/006-minimax-asr-llm/
├── plan.md              # 本实施计划
├── research.md          # Phase 0 调研与技术决策 (R1~R8)
├── data-model.md        # Phase 1 数据模型映射 (MiniMaxWordItem, BrollCueItem)
├── quickstart.md        # Phase 1 自动化与手动走查验证指南
├── contracts/           # Phase 1 接口契约
│   └── api.md           # MiniMax STT、Cue Sheet Chat Completion 与 Settings API 契约
└── checklists/
    └── requirements.md  # 需求质量检查清单 (16/16 全绿)
```

### Source Code Layout

```text
backend/
├── app/
│   ├── api/
│   │   ├── editor.py            # 主剪辑流水线：对接稀疏分镜决策与双层 60%~70% 编排
│   │   └── settings.py          # ASR Provider 设置与连通性检测接口
│   ├── core/
│   │   └── config.py            # 读取 settings.json 中的 minimax/asr 配置
│   ├── harness_bridge/
│   │   ├── api_engine.py        # 稀疏分镜 Cue Sheet 调用与 <300 Token 流式解析
│   │   └── prompting.py         # 重构 build_scene_decision_prompt (删除消极锁死规则)
│   └── native_engine/
│       ├── asr_runner.py        # 废除 14 字硬切，支持词尾标点感知与 8~18 字意群弹性合并
│       └── scene_decision.py    # 强相关精准绑定 + 自由段落随机铺底至 60%~70% + 禁切红线保护
tests/
├── test_minimax_asr.py          # MiniMax ASR 单元测试、词尾标点提取与离线降级测试
├── test_scene_decision_cue.py   # [NEW] 稀疏 Cue Sheet 解析、60%~70% 覆盖率与禁切区单测
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
| **稀疏剪辑指示清单 (Editorial Cue Sheet)** | 将大模型输出 Token 压缩 95%，彻底解决 4800 Token 截断导致的 0% 分镜崩盘 | 逐句打标（59 题填空）必然触碰单次生成上限；分批次调用则过于复杂且耗时增加 4 倍 |
| **自然意群切分与 8~18 字弹性合并** | 消除“千万不 / 要报”词组腰斩与 0.4s 微短碎片，保证中文一句话或半句话语法完整 | 14 字机械硬切无视中文语法；纯停顿切分无法控制单行长度 |
| **强相关精准匹配 + 自由段落随机铺底 (60%~70%)** | 1~2 分钟短视频需 15~20 个空镜（72~84 秒），兼顾重点语段真实对应与高频视听节奏 | 纯靠 AI 挑 20 条会再次爆 Token；纯等间隔机械切入则缺乏场景相关性 |
| **三大禁切区绝对锁定 (开场真人/报价/CTA)** | 保障口播短视频商业转化（开场建信任、手势报价是内容本体、结尾促转化） | 若允许 AI 随意覆盖开场或手势，会导致关键商业信息和手势画面丢失 |