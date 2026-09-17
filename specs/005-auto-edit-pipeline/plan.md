# Implementation Plan: 智能剪辑与自动分镜流水线

**Branch**: `005-auto-edit-pipeline` | **Date**: 2026-09-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-auto-edit-pipeline/spec.md`

## Summary

把现行「智能初剪辑」升级为完整智能剪辑流水线：界面动作收敛为「智能剪辑」单一按钮并移除单步纠错；高亮词升级为「词库兜底 ∪ AI 判定 ∪ 手动编辑」三源合并并在字幕时间轴上可视化调整；素材分镜体系迁移为四类（口播/场地/体验/教学，medical→experience 数据迁移）；新增 AI 分镜决策（切哪类、切多久、转场多久，转场只切画面音轨不动）；补批量剪辑队列与单视频工作台联动；标题水印默认关闭；封面字段与接口预留。AI 链路可行性已真实实测验证（research.md R1/R2 含 glm-5.3-flash 直连与 codex 代理的完整对比数据）。

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI) / TypeScript (React 18 + Vite)
**Primary Dependencies**: FastAPI、faster-whisper、FFmpeg/FFprobe、Pydantic v2、httpx、React、TailwindCSS、lucide-react
**Storage**: SQLite `storage/videocut.db`（权威）+ storage/ 素材与产物文件
**Testing**: pytest（66 现有用例基线，conftest 已隔离临时库）
**Target Platform**: Windows 桌面壳（launcher.py，127.0.0.1:18888），macOS 规划中
**Project Type**: 本地桌面 Web 应用（FastAPI + React SPA）
**Performance Goals**: 单视频全流水线（27s 素材）≤ 3 分钟（AI 决策放宽超时后）；批量按硬件并发线性扩展
**Constraints**: AI 调用 timeout ≤120s；转场不得改动音轨；所有失败路径如实报错（真实执行铁律）；凭据零明文出后端
**Scale/Scope**: 单机单用户；本次 8 个用户故事、2 次迁移（DB CHECK 重建 + 磁盘目录）、3 个新端点

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 评估 |
|---|---|
| I. C端体验免终端 | ✅ 全部改动经 GUI；迁移脚本为开发期工具（沿用 apply_glossary.py 惯例） |
| II. Harness 抽象解耦 | ✅ 分镜决策走 `prompting.py` 统一提示词工厂 + 统一 JSON 校验；api/codex 引擎共用 `llm_client`；Tier B 规则不变 |
| III. 智能音视频管线 | ✅ 核心增强：声画解耦保持（IR4 音轨恒为口播）；关键词驱动升级为「关键词规则（降级路径）+ AI 决策（主路径）」；全部结果界面可逆微调 |
| IV. 硬件感知并发 | ✅ 批量队列并发取 recommended_concurrency；失败如实落库 |
| V. 极简防无用循环 | ✅ 不引入新框架/组件库；复用现有字幕卡片、composer 管线、迁移脚本惯例 |

**Post-design re-check**: 无违反。embedded 引擎保持仅词库确定性能力，AI 决策失败降级路径最终落到现行关键词规则，不新增 Stub。

## Project Structure

### Documentation (this feature)

```text
specs/005-auto-edit-pipeline/
├── plan.md              # 本文件
├── research.md          # AI 实测证据与技术决策
├── data-model.md        # 实体变更与迁移设计
├── quickstart.md        # 端到端验证指南
├── contracts/
│   └── api.md           # 新增/变更 API 契约
└── tasks.md             # Phase 2 输出（/speckit-tasks 生成，本命令不创建）
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── editor.py          # [改] 智能剪辑全流程接入分镜决策；/scene-decision、/cover 新端点
│   │   ├── batch.py           # [新] 批量任务 submit/status
│   │   └── materials.py       # [改] experience 分类标签
│   ├── harness_bridge/
│   │   ├── prompting.py       # [改] 新增 build_scene_decision_prompt()（词库驱动）
│   │   ├── codex.py           # [改] 修 active_model NameError；决策调用通道
│   │   ├── api_engine.py      # [改] 决策调用实现（timeout 120s）
│   │   └── llm_client.py      # [改] /responses 备用仅限本地 codex 代理
│   ├── models/entities.py     # [改] HighlightWord/SceneDecision/BatchJobItem/cover 字段/枚举迁移/默认值
│   ├── db/
│   │   ├── schema.sql         # [改] materials CHECK、batch_jobs 表
│   │   └── session.py         # [改] 005 迁移段（静态 DDL 惯例）
│   └── native_engine/
│       ├── keyword_matcher.py # [改] experience 键 + 高亮词三源合并工具
│       ├── ffmpeg_filter.py   # [改] xfade 转场档（fade）；横幅水印默认关闭路径
│       └── subtitle_styler.py # [改] 高亮词数据源切换 highlight_words
frontend/src/
├── pages/VideoEditor.tsx      # [改] 按钮收敛「智能剪辑」、删单步纠错、分镜进度阶段
├── components/SubtitleList.tsx# [改] 高亮词 chip（来源徽标/增删）
├── components/StrategyStudio.tsx # [改] 转场档开关；横幅水印区块默认折叠关闭
├── pages/AssetLibrary.tsx     # [改] 四类分镜标签与批量入口
└── services/api.ts            # [改] 新端点封装
scripts/
└── migrate_005.py             # [新] 幂等迁移（试运行/--apply）
tests/
├── test_scene_decision.py     # [新] 决策 JSON 校验裁剪/降级
├── test_batch_api.py          # [新] 批量契约
└── （存量 66 用例全部保持通过）
```

## Implementation Phases（关键路径）

### Phase A — 界面收敛与缺陷修复（低风险先行）
1. VideoEditor.tsx：按钮文案「智能剪辑」（两处状态）、删除单步纠错按钮块与 `handleCorrectSubtitles` 调用（`/correct` 后端保留）。
2. codex.py `active_model` NameError 修复；llm_client `/responses` 备用仅限本地代理来源。
3. entities：banner/watermark 默认 False（仅影响新建工程）。

### Phase B — 高亮词三源合并 + 时间轴可视化（Story 2/3）
1. entities：`HighlightWord`、`SubtitleSegment.highlight_words`；bridges 回填逻辑升级（AI 词 source="ai"，词库 source="glossary"）。
2. subtitle_styler 渲染数据源切换；存量 `matched_keywords` 兼容读取。
3. SubtitleList.tsx chip 组件 + PUT subtitles 持久化（手动 source="manual"）。

### Phase C — 四类分镜迁移（Story 4）
1. scripts/migrate_005.py（DB CHECK 重建 + 目录 + glossary 键 + legacy 备份，试运行/--apply）。
2. 代码面枚举/映射/标签同步（backend 全局 medical 引用清单见 data-model.md §1）。

### Phase D — AI 分镜决策（Story 5，本特性核心）
1. prompting.build_scene_decision_prompt()（词库背景 + 精简字幕 + 严格 JSON 样例）。
2. api_engine/codex 通道实现 + 120s 超时 + 结果校验裁剪（broll 枚举、duration≤句长、transition≤0.5）+ 失败降级关键词规则。
3. editor.py 全流程第 3.5 步接入、`SCENE_DECIDING` 进度档、`scene_decision` 持久化；新端点 `/scene-decision` 重跑。
4. ffmpeg_filter xfade 档：相邻片段 `xfade=fade:d={transition}:offset=...` 链式串联，音轨 `map 0:a` 不动；`transition_style="cut"` 走现状 concat。

### Phase E — 批量剪辑 + 封面（Story 6/8）
1. batch_jobs 表 + api/batch.py（submit/status，硬件并发节流，失败真实落库）。
2. AssetLibrary 批量入口与队列 UI（复用 progress 组件）。
3. cover 字段 + `/cover` 截帧（ffmpeg -ss 帧提取）/上传端点；AI 入口 501 规划中提示。

## Risks & Mitigations

| 风险 | 缓解 |
|---|---|
| AI 决策超时（实测直连 60s 失败） | timeout 120s + 输出 token 精简 + 批量并行掩盖延迟 + 降级规则兜底 |
| xfade 滤镜链复杂度/时长对齐 | fade 档独立开关，cut 档始终可用；offset 逐段累计计算并做浮点容错 |
| medical→experience 迁移破坏存量 | 幂等脚本 + legacy 备份 + 读取端 medical→experience 兼容映射一层 |
| 存量工程策略默认值被改写 | 默认值仅作用于新建工程，迁移不触碰已保存策略 |
| 凭据泄漏 | 新端点不触碰 settings 凭据读取路径；契约 C6 保持红线 |

## Note for tasks phase

- 顺带修复项（R6）：codex NameError、llm_client 备用端点浪费 —— 已列入 Phase A。
- 测试边界：所有断言 LLM 输出的用例固定 embedded 词库引擎或 mock 响应（AGENTS.md 测试数据边界）。
