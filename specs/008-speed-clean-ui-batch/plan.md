# Implementation Plan: 视频编辑倍速、Taste UI 极简去繁与批量混剪工作台重构 (008-speed-clean-ui-batch)

**Branch**: `008-speed-clean-ui-batch` | **Date**: 2026-09-19 | **Spec**: [specs/008-speed-clean-ui-batch/spec.md](specs/008-speed-clean-ui-batch/spec.md)

**Input**: 用户指令：“然后选择一下视频可以编辑的倍速，新增加功能的话要考虑页面的美观，用一下taste skill https://github.com/Leonxlnx/taste-skill, 再考虑一下删除页面上无意义的模块，以及对功能无意义的解释，把这些删除掉，保持最清洁，功能完善的页面，批量混剪页面也要好好设计，你作为一个10年经验的页面设计专家和产品经理，再设计一下怎么表达效果是最好的”

---

## Summary

本功能围绕四大核心支柱展开：
1. **视频编辑与压制倍速（Video Speed Control）**：在 `EditingStrategy` 落地 `video_speed`（1.0x/1.1x/1.15x/1.2x/1.25x），通过 FFmpeg `atempo`（锁定原调，不产生尖锐花栗鼠声）与 `setpts` 高质加速，并将所有字幕起止时间与空镜切片时间除以倍速等比缩放，实现声画、字幕、高亮词与空镜 100% 同步紧凑；播放器同步支持实时播放倍速快捷切换。
2. **Taste-Skill 前端反油腻与极简去繁**：应用 `design-taste-frontend` 顶级审美准则，彻底删除页面上的冗余解释文案、自嗨式状态段落、括号括注与花哨渐变，收敛为中性白灰基底 + 单一 Indigo 品牌色，采用现代 Segmented Switch 替代臃肿横条。
3. **10年资深专家级批量混剪工作台（BatchCut）重构**：打造“生产驾驶舱”架构，引入顶部 Command Bar 批处理控制台、成片画廊（Gallery）与任务队列（Queue）双模态工作区，极简收纳硬件监控指标，提供真正专业高能效的批量生产体验。

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.x, React 18, Tailwind CSS v4, FFmpeg 6.x  
**Primary Dependencies**: FastAPI, Pydantic v2, Lucide Icons, Axios, Vite  
**Storage**: SQLite 权威库 `storage/videocut.db`，项目目录 `storage/tasks/{YYYYMMDD_HHMMSS}_{stem}/`  
**Testing**: pytest (Python), pnpm build (Frontend TypeScript)  
**Target Platform**: Windows 11 / Desktop Web & Electron  
**Project Type**: Web Desktop Video Production Workstation  
**Performance Goals**: 视频加速压制无额外二次转码耗时；批量混剪按硬件推荐并发槽位调度；前端交互响应 < 16ms  
**Constraints**: 绝不允许使用 mock 或降级假装加速；真实素材 > 10KB 失败必须如实抛出；遵循 Taste Skill 审美原则  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I. C端体验与免终端启动**: 所有倍速选择、去繁控制与批量队列在 Web GUI 呈现，绝无未捕获终端黑框。
- [x] **II. Harness 抽象与引擎解耦**: 视频倍速与页面美学重构属于原生渲染与 UI 展现层，不破坏底层 LLM/ASR Harness 契约。
- [x] **III. 智能音视频管线与声画解耦**: `video_speed` 应用于 FFmpeg filtergraph 时严格保证口播原声保调（`atempo`）与空镜切点等比缩放，声画严密对齐。
- [x] **IV. 硬件感知与批处理并发调度**: 批量混剪保留根据 CPU/内存动态调整并发槽位能力，但 UI 层面收纳为极简状态芯片，消除 4 块臃肿大卡片对工作区的干扰。
- [x] **V. 极简高效与防无用循环**: 坚持减法原则，删除多余解释与冗长文案，代码简洁，无多余抽象。

---

## Project Structure

### Documentation (this feature)

```text
specs/008-speed-clean-ui-batch/
├── spec.md              # 需求规格说明书
├── plan.md              # 本实施方案
├── research.md          # Phase 0 研究记录与决策依据
├── data-model.md        # Phase 1 数据模型
├── contracts/           # Phase 1 契约 (api.md)
└── quickstart.md        # Phase 1 验证指南
```

### Source Code

```text
backend/app/
├── models/entities.py            # EditingStrategy.video_speed 字段与校验
├── native_engine/ffmpeg_filter.py # compose_jl_cut 变速滤镜（atempo + setpts + 字幕/空镜等比缩放）
├── api/editor.py                 # 初剪与渲染策略透传 video_speed
└── api/batch.py                  # 批量上传与执行支持 video_speed

frontend/src/
├── services/api.ts               # EditingStrategy.video_speed 与批量接口参数
├── components/
│   ├── StrategyStudio.tsx        # 语速与节奏面板（倍速选择），彻底去繁清减冗余文字
│   ├── VideoPlayer.tsx           # 播放器倍速按钮（0.75x~2.0x）
│   └── SubtitleList.tsx          # 去除多余括号与冗长注释
└── pages/
    ├── VideoEditor.tsx           # Segmented Switch 模式切换，精简按钮文案，去自嗨式提示
    └── BatchCut.tsx              # 10年资深专家级批量生产驾驶舱（Command Bar + 画廊/队列双模）
```

---

## Detailed Implementation Tasks

### 1. 后端视频变速与等比时间轴缩放 (Backend Engine)
1. **实体升级** (`backend/app/models/entities.py`):
   - 在 `EditingStrategy` 增加 `video_speed: float = 1.0`（0.75 ≤ speed ≤ 2.0，默认 1.0）。
2. **合成器滤镜与字幕/空镜等比缩放** (`backend/app/native_engine/ffmpeg_filter.py`):
   - 在 `compose_jl_cut` 中读取 `speed = float(strategy.get("video_speed") or 1.0)`；
   - 若 `speed != 1.0`:
     - 缩放总时长：`scaled_total_duration = total_duration / speed`；
     - 缩放空镜切片时间：`broll_cuts` 的 `start_time` 和 `end_time` 分别除以 `speed`；
     - 视频流应用 `setpts=(1.0/speed)*PTS`；
     - 音频流应用 `atempo=speed`（当 speed ≤ 2.0 时单级 atempo 即可稳定保调）；
     - 生成的 ASS / SRT 字幕时间戳直接按缩放后的时间生成；
3. **批量混剪接口支持** (`backend/app/api/batch.py`):
   - `upload_and_cut` 接口支持 `video_speed: float = Form(1.0)`；
   - 在批处理作业执行单片分析剪辑时，将该倍速注入 `project.strategy.video_speed`。

### 2. 前端 Taste-Skill 界面美化与彻底去繁 (Frontend Taste UI)
1. **策略工坊精炼与倍速控制** (`frontend/src/components/StrategyStudio.tsx`):
   - 新增「语速与节奏 (Speed)」卡片，提供快捷档位胶囊（`1.0x 正常原速`、`1.1x 紧凑微快`、`1.15x 轻快顺畅`、`1.2x 节奏干脆`、`1.25x 极速快嘴`）；
   - 彻底删除无意义的说明段落与占位废话，各模块紧凑呼吸。
2. **播放器即时倍速切换** (`frontend/src/components/VideoPlayer.tsx`):
   - 控制条右侧新增轻量倍速选择器（`1.0x` / `1.25x` / `1.5x` / `2.0x`），联动 `videoRef.current.playbackRate`。
3. **剪辑工作台去繁净化** (`frontend/src/pages/VideoEditor.tsx`):
   - 将原占位的蓝色长条提示替换为现代 Segmented Control：`[ 实时编辑 | 成片预览 ]`；
   - 优化按钮标签：`智能初剪`、`导出成片`、`上传封面`、`截取封面`；
   - 清理所有无意义的括号说明与 AI 自夸文本。
4. **批量混剪页面（BatchCut.tsx）重构升级**:
   - 顶部集成紧凑 Command Bar（画幅选择、倍速切换、并发设置、添加视频）；
   - 双模态视图切换：
     - **成片画廊（Gallery，默认）**：卡片式展现所有剪辑成果，支持 Hover 预览播放、一键微调、打开目录；
     - **混剪队列（Queue）**：当前批次任务执行进度条与分步状态。
   - 4 块大硬件指标收缩为极简状态胶囊。

---

## Verification Plan

### Automated Tests
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; uv run pytest tests/test_subtitle_strategy.py tests/test_editor_api.py tests/test_batch_api.py
$env:NO_UPDATE_NOTIFIER='1'; $env:CI='1'; pnpm build; exit $LASTEXITCODE
```

### Manual Verification
1. 载入真实素材，设置 1.15x 倍速并导出，核验音频音调自然正常，时长缩短至 1/1.15，字幕与真人加速发音严格同步。
2. 查看剪辑工作台与批量混剪页面，核验界面纯净通透，无冗余说明文字，成片画廊交互流畅。