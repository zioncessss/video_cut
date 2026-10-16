# Implementation Plan: 自主分镜切入裁剪与字幕重叠定位原口播视频误读裁剪 (Storyboard Trim & Subtitle Retake Pruning)

**Branch**: `016-storyboard-trim-sub-retake-prune` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-storyboard-trim-sub-retake-prune/spec.md`

## Summary

实现口播视频高精度智能剪辑与单页极简交互体系：
1. **智能误读识别与物理裁剪**：在 ASR 阶段设立短句重读阻断守卫（防粘连），在粗剪算法中引入前缀重叠比对（$\ge 75\%$）与三重防误剪安全网；用户或算法确认剔除后，对原口播视频执行基于 `kept_spans` 的 `trim+atrim+concat` 音画真实物理剪裁与 15ms 平滑淡入淡出（防爆音），字幕向左平移对齐，严禁只删文字假装裁切。
2. **分镜自主截取与切入**：扩展 `BrollReplacement` 支持素材截取 In 点 (`source_start_time`)，分镜强制静音剥离音频作为纯画面覆盖，原口播音频作为连续旁白贯穿。
3. **单页内联极简与实时所见即所得**：抛弃繁复时间轴大弹窗，在卡片内就地完成分镜截取与字幕微调；被裁卡片就地折叠为浅灰微条并提供“恢复”按钮；播放器实现虚拟跳播（Virtual Jump-Cut）与分镜实时贴片，预览延迟 $<50ms$。

## Technical Context

**Language/Version**: Python 3.11+ (Backend), TypeScript 5.0+ / React 18 (Frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy, SQLite (Local Authority), FFmpeg 6.0+, Vite, Tailwind CSS, Lucide React

**Storage**: SQLite 权威存储 (`storage/videocut.db`)，工程表与分镜表，严禁直改 shadow json

**Testing**: pytest (`.\.venv\Scripts\pytest.exe`), Vitest

**Target Platform**: Windows 10/11 桌面环境 (免终端一键启动)

**Project Type**: Desktop Hybrid App (Electron + FastAPI + React)

**Performance Goals**: 剪辑实时预览延迟 $< 50\text{ms}$，短句口误识别准确率 $\ge 95\%$，误剪率 $\le 1\%$

**Constraints**: 
- 严格遵循真实工程运行准则，严禁静默 fallback 或假剪辑；
- 遵循 Anti-Slop 极简原则，界面杜绝多余提示与弹窗；
- 全生命周期保证高亮词 100% 不丢失与自愈。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章原则 | 检查结论 | 合规细节 |
| :--- | :--- | :--- |
| **I. C端免终端启动** | **PASS** | 全部功能均在现有单页 Web 工作台内直接交互，零终端命令暴露给用户。 |
| **II. Harness 解耦** | **PASS** | 物理剪辑与 ASR 算法属于 Native Engine，与 Harness 纠偏桥接器解耦。 |
| **III. 智能声画解耦管线** | **PASS** | 明确口播原声为主旁白、分镜素材强制静音剥离、真实物理切片拼接。 |
| **IV. 硬件感知与并发** | **PASS** | 导出合成继续复用单作业/受限并发调度器，防止 GPU/CPU 爆满。 |
| **V. 极简高效防过度设计** | **PASS** | 杜绝多轨时间轴与大弹窗，采用卡片内联调节与浅灰微条折叠。 |

## Project Structure

### Documentation (this feature)

```text
specs/016-storyboard-trim-sub-retake-prune/
├── spec.md              # 需求规格说明书 (含 3 项深度澄清决策)
├── plan.md              # 本技术实施计划
├── research.md          # Phase 0 算法选型与决策
├── data-model.md        # Phase 1 实体定义与字段扩展
├── contracts/           # Phase 1 接口契约
│   └── editor-contracts.md
├── quickstart.md        # Phase 1 验证场景与测试指令
├── checklists/          # 需求完整性检查清单
│   └── requirements.md
└── tasks.md             # Phase 2 任务清单 (由 /speckit-tasks 生成)
```

### Source Code (repository root)

```text
backend/app/
├── native_engine/
│   ├── asr_runner.py          # ASR 短句合并重读阻断守卫 (Retake Guard)
│   ├── prune_engine.py        # 口误前缀重叠比对 (>=75%) 与三重防误剪安全网
│   └── ffmpeg_filter.py       # 分镜 source_start_time 裁剪与 kept_spans 物理拼接
├── models/
│   └── project.py             # BrollReplacement 实体增加 source_start_time
├── schemas/
│   └── project.py             # API 校验 Schema 扩展
└── api/
    └── editor.py              # 字幕、分镜与裁剪状态统一更新接口

frontend/src/
├── components/
│   ├── VideoPlayer.tsx        # 虚拟跳播 (Virtual Jump-Cut) 与实时分镜贴片覆盖
│   └── SubtitleList.tsx       # 卡片就地分镜调节、浅灰微条折叠收纳与恢复按钮
└── pages/
    └── VideoEditor.tsx        # 状态流转与单页集成

tests/
├── test_asr_retake_guard.py   # ASR 重读防粘连单元测试
├── test_prune_retake_prefix.py# 前缀重叠算法与防误剪测试
├── test_broll_source_trim.py  # 分镜 In 点截取测试
└── test_prune_video_export.py # 原视频物理音画裁剪集成测试
```

**Structure Decision**: 采用现有前后端分离架构，直接在已有的 `native_engine` 与前端核心组件中做精准内联修改，绝不引入多余的空层抽象。

## Complexity Tracking

> **Constitution Check 100% 遵从，无违背项，无需额外复杂性声明。**
