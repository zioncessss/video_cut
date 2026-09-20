# Implementation Plan: 智能剔除口播视频头尾动作与口误重说 (009-prune-retakes-silence)

**Branch**: `009-prune-retakes-silence` | **Date**: 2026-09-20 | **Spec**: [specs/009-prune-retakes-silence/spec.md](spec.md)

**Input**: Feature specification from `/specs/009-prune-retakes-silence/spec.md`

## Summary

本特性为手机录制的口播毛片构建全自动智能粗剪管线（Auto Prune Pipeline）。针对手机口播特有的开机准备废动作（0.8s~3.7s）、尾部伸手关机废动作（1.1s~2.3s）、卡壳口误重说（留后弃前）以及中途看稿长停顿（>1.2s），在 ASR 语音转写后、空镜匹配前自动计算剔除区间。特别遵循**“保留人类自然呼吸停顿（0.25s~0.35s）”**原则，杜绝非人性化极度硬切；在剪辑工作台提供 0 延迟虚拟跳播与完全可逆微调；在 FFmpeg 视频导出时实现声画严格切除与微秒级音频防爆音平滑拼接。

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.0+, React 18, Node 18+ (Electron)  
**Primary Dependencies**: FastAPI, SQLite3, FFmpeg, difflib (Python 标准库), Pydantic v2, Lucide-React, TailwindCSS  
**Storage**: SQLite (`storage/videocut.db`) 权威存储，新增 `prune_spans_json` 与 `is_pruned` 字段  
**Testing**: pytest (覆盖算法、真实工程回归、FFmpeg 滤镜与防爆音)  
**Target Platform**: Windows 10/11 & macOS 桌面端 (Electron 封装)  
**Project Type**: Desktop Hybrid App (Electron + Vite React + FastAPI Local Backend)  
**Performance Goals**: 5 分钟口播视频粗剪分析耗时 < 50ms；前端跳播 0 延迟实时响应；成片导出耗时增加量为 0（仅增减 filter 节点）  
**Constraints**: 
1. 严禁 0 间隙机关枪式紧切，严格保留 0.25s~0.35s 自然生理呼吸间隙；
2. ASR 原文字幕不可篡改，剔除操作 100% 非破坏性（可随时一键恢复）；
3. FFmpeg 音频切口处必须有平滑微消隐（afade 15ms），杜绝电平跳跃产生的爆音（Click/Pop）；
4. 纯确定性算法优先（difflib + 时间轴物理特征），离线可用、无额外 API Token 成本。

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Gate I: C端体验与免终端启动 (Zero-Terminal Launch)**: PASS. 全部粗剪状态在界面通过高亮/划线直观呈现，微调在时间轴与字幕列表通过图形化点击完成，无终端依赖。
- **Gate II: Harness 抽象与引擎解耦**: PASS. 粗剪逻辑作为 native_engine 的纯函数/服务层，不绑定具体 LLM 桥接器，保持引擎解耦。
- **Gate III: 智能音视频管线与可逆微调 (Constitution Principle III)**: PASS. 核心满足“所有自动生成的切片区间与字幕文本均必须允许用户在界面二次编辑与微调”。
- **Gate IV: 硬件感知与批处理调度**: PASS. 纯算法内存计算，CPU 开销微乎其微，完美融入批处理流水线。
- **Gate V: 极简高效与防过度工程 (Ponytail & Constitution Principle V)**: PASS. 采用 Python 内置 `difflib` 与数学区间运算，零额外第三方大重库依赖，代码短小精悍。

---

## Project Structure

### Documentation (this feature)

```text
specs/009-prune-retakes-silence/
├── spec.md              # 需求规格说明书
├── plan.md              # 本实施计划文件
├── research.md          # 决策与算法调研（Phase 0）
├── data-model.md        # 数据模型与 SQLite 迁移（Phase 1）
├── quickstart.md        # 快速验证与测试指南（Phase 1）
├── contracts/
│   └── prune-engine-contract.md # 服务与 API 契约（Phase 1）
└── checklists/
    └── requirements.md  # 规格质量检查清单
```

### Source Code

```text
backend/app/
├── native_engine/
│   ├── prune_engine.py          # [NEW] 核心粗剪算法引擎（头尾/重说/气口压缩）
│   ├── ffmpeg_filter.py         # [MODIFY] 支持基于 kept_spans 的音画精准切除与 afade 防爆音
│   └── scene_decision.py        # [MODIFY] 空镜决策自动规避已剔除区间
├── api/
│   ├── editor.py                # [MODIFY] 增加 toggle-prune 与微调 API
│   └── batch.py                 # [MODIFY] 自动剪辑流水线集成 AutoPruneEngine
├── models/
│   └── entities.py              # [MODIFY] 扩展 PruneSpan, EditingStrategy 配置项
└── db/
    ├── schema.sql               # [MODIFY] 库表增加 prune_spans_json 与 is_pruned
    └── repository.py            # [MODIFY] 支持剔除状态的查询与持久化更新

frontend/src/
├── components/
│   ├── VideoPlayer.tsx          # [MODIFY] 实现虚拟跳播 (Virtual Skip) 与剔除进度条渲染
│   └── SubtitleList.tsx         # [MODIFY] 字幕条目增加【已剔除】划线展示与【恢复/剔除】按钮
└── services/
    └── api.ts                   # [MODIFY] 补充粗剪相关前端数据接口
```

---

## Implementation Phases & Plan Details

### Phase 0: Research & Feasibility (Completed)
- 调研手机口播视频的物理发音与动作习惯；
- 基于 5 部真实工程素材总结 4 大规律并确定气口计算模型（0.25s~0.35s 人性化停顿保留）；
- 输出 [research.md](research.md)。

### Phase 1: Design & Contracts (Completed)
- 建立 `PruneSpan`、`PruneStrategyConfig` 与 `KeptSpan` 数据模型；
- 输出 [data-model.md](data-model.md)、[contracts/prune-engine-contract.md](contracts/prune-engine-contract.md)、[quickstart.md](quickstart.md)；
- 更新 `AGENTS.md` 上下文。

### Phase 2: Core Algorithm Engine (`prune_engine.py`)
- 实现 `AutoPruneEngine.analyze_and_prune`：
  1. **头部动作检测**：定位 `first_speech.start_time`，保留 `head_padding_seconds`（默认 0.20s），将 `[0.0, first_speech.start_time - 0.20s]` 生成 `head_idle` 剔除区间；
  2. **尾部动作检测**：定位 `last_speech.end_time`，保留 `tail_padding_seconds`（默认 0.25s），将 `[last_speech.end_time + 0.25s, video_duration]` 生成 `tail_idle` 剔除区间；
  3. **口误重说检测 (留后弃前)**：滑动窗口比对 `sub[i]` 与 `sub[i+1]`（或跨度 2 句）：
     - 若停顿在 `0.4s ~ 1.5s` 且文本相似度/公共子串覆盖率 >= 60%，判定为口误重讲；
     - 将 `sub[i]` 标记为 `retake_discard` 剔除，在保留句前预留 0.20s 自然起音缓冲；
     - 处理连续重说链（向前追溯全部未完成前置句）；
  4. **中段长静音压缩**：若 `gap = sub[i+1].start_time - sub[i].end_time > 1.2s` 且非重说，计算剔除区间 `[sub[i].end_time + 0.15s, sub[i+1].start_time - 0.15s]`，精确保留 0.30s 自然换气停顿。
- 实现 `compute_kept_spans`：将所有生效的 `prune_spans` 取反，输出不重叠递增的 `kept_spans`。

### Phase 3: Pipeline & Storage Integration
- 修改 `schema.sql` 与 `repository.py`：支持 `prune_spans_json` 和 `is_pruned` 的保存与读取；
- 修改 `batch.py` 自动剪辑主任务：在 `asr_runner.transcribe` 生成字幕后，立即调用 `AutoPruneEngine` 进行粗剪标记，再存入数据库并流转至后续步骤。

### Phase 4: FFmpeg Multi-Track Export Adaptation
- 修改 `ffmpeg_filter.py` 中的 `compose_multi_track_video`：
  1. 视频轨基于 `kept_spans` 进行 `trim=start:end` 裁剪与 `concat` 拼接；
  2. 音频轨基于 `kept_spans` 进行 `atrim` 裁剪，并在每个片段首尾注入 `afade=t=in:ss=0:d=0.015,afade=t=out:st={dur-0.015}:d=0.015` 微衰减，消除拼接爆音；
  3. 空镜切片与字幕时间轴按 `kept_spans` 累加偏移映射，保证完全同步。

### Phase 5: Frontend Interactive Preview & Polish
- 修改 `VideoPlayer.tsx`：
  - 监听播放进度，当前时间落入 `prune_spans` 时自动跃迁（Virtual Skip）；
  - 进度条底部渲染半透明暗红色阴影条带标识剔除区间；
- 修改 `SubtitleList.tsx`：
  - 被剔除的字幕项呈现灰色中划线并标注原因徽章（如“口误重说”、“头部动作”）；
  - 提供【恢复/保留】开关按钮，点击后通过 API 即时更新状态。

### Phase 6: Automated Verification & Project Regression
- 编写单测 `tests/test_auto_prune_engine.py`；
- 使用数据库内现有的 5 部真实口播视频作为基准测试，断言头部、尾部与重说句（如《湖州驾校》第 0 句、《经常有评论》第 17 句）准确剔除且气口保留在 0.25s~0.35s。

### Phase 7: Pipeline Reordering — Prune-First Scene Scheduling (先粗剪后分镜排期重构)
- **核心目标**：彻底解决片头裁剪后开场 Hook 禁切规则失效、成片空镜覆盖率超标以及跨切点断裂问题。
- **流水线改造 (`editor.py`)**：
  1. 在 `analyze_and_cut` 中，ASR 与纠错后立即执行粗剪并计算 `kept_spans` 与 `effective_duration`；
  2. 调用 `reproject_subtitles_to_compact` 生成以 `0.0s` 为起点的紧凑成片字幕列表；
  3. 将紧凑成片字幕与 `effective_duration` 作为分镜决策的输入：
     - 开场禁切区（前 1.8s ~ 2.0s）在真实成片起点严格生效，杜绝成片开场被大空镜覆盖；
     - 空镜 65% 目标覆盖率以 `effective_duration` 真实成片时长精准计算；
     - 空镜窗口直接锚定紧凑时间轴，生成无切点断裂的 `BrollReplacement`；
  4. 同步改造 `redecide_scenes` 接口，保证二次编排分镜同样基于紧凑时间轴；
  5. 视频渲染器 `render_project` 直接消费紧凑分镜，无需运行时二次逆向映射。
- **回归与实测**：
  - 更新《湖州驾校大改革》分镜与渲染，验证开场 1.8s 主播真人露脸亮相与 65% 黄金覆盖率；
  - 运行全量 151+ 项单测与前端编译。

### Phase 8: Batch Cut De-Speeding & Video-Composition Auto-Concurrency (批量去倍速与合成自主并发)
- **核心目标**：消除批量混剪全局倍速干扰（回归单视频策略面板精调），解绑本地 ASR 限制，建立基于视频合成真实物理开销的自主并发调度算法，免除用户心智负担。
- **设计与实现**：
  1. **前端界面改造 (`BatchCut.tsx`)**：
     - 从顶部 Command Bar 移除 `倍速:` 控件与 `并发:` 手动输入框；
     - 上传模态框移除剪辑倍速与并发选项，批量创建默认采用 1.0x 标准语速；
     - 硬件 Badge 升级为自适应调度展示：`⚡ 智能并发: {hardware.recommended_concurrency}路 · {hardware.cpu_cores}核 · {hardware.gpu_accelerator_detected ? 'GPU加速' : 'CPU'}`；
  2. **后端资源算法 (`resource.py` & `batch.py`)**：
     - 彻底解绑 Whisper 本地内存预算；
     - 纯按视频合成（FFmpeg filter_complex、解码、NVENC/x264 编码、Lanczos 缩放、内存）开销进行规划：
       - GPU 加速：`max(1, min(cores // 2, int(mem_avail_gb // 0.8), 4))`；
       - CPU 软解：`max(1, min(cores // 3, int(mem_avail_gb // 1.2), 3))`；
     - 批处理任务执行队列自动应用计算出的 `recommended_concurrency` 作为全局并发信号量。


