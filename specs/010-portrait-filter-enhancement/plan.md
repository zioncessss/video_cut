# Implementation Plan: 真实人物口播视频滤镜画质调优与最佳剪辑效果 (portrait-filter-enhancement)

**Branch**: `010-portrait-filter-enhancement` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-portrait-filter-enhancement/spec.md`

---

## Summary

针对手机录制的真实人物出镜口播视频，通过深度调研与技术实测，确立并落地行业顶级的口播画质处理方案：
1. **解决“是否需要锐化”**：明确界定“必须微锐化以对抗短视频平台二次压缩，但严禁全局大核强锐化（会导致脏脸、毛孔粗大、白边光晕）”，采用 AMD FidelityFX **CAS (Contrast Adaptive Sharpening)** 对比度自适应锐化算法，在平坦皮肤处自动抑制锐化，在发丝、眼神光、唇线等边缘施加精准微锐化（强度 0.25~0.35）。
2. **三阶微调复合管线**：`微质感平滑 (smartblur 负阈值微平滑) -> 通透暖润肤色调优 (eq 对比+4%、亮度+0.02、微拉 Gamma 提亮中间调人脸、微增饱和度) -> 自适应微锐化 (cas)`。
3. **4 档专属预设**：
   - `clean_natural`（自然通透·默认推荐）
   - `crisp_hd`（质感超清）
   - `warm_radiant`（元气暖肤）
   - `original`（原色无滤镜·Bypass）
4. **全链路架构融合**：扩展 `EditingStrategy` 实体，升级 `FFmpegFilterComposer`，并在 Web 剪辑工作台右侧策略面板提供直观的预设选择与强度滑块，保障成片导出秒级生效。

---

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI / Pydantic v2 / SQLite) & TypeScript / React (Tailwind CSS, Lucide Icons)  
**Primary Dependencies**: FFmpeg 8.1.2 (built with `cas`, `unsharp`, `smartblur`, `eq`), FastAPI, Pydantic, Pillow  
**Storage**: SQLite 权威存储 (`storage/videocut.db`) + 专属任务目录序列化 (`project_manifest.json`)  
**Testing**: pytest (`tests/test_portrait_filters.py`) + 端到端视频压制断言  
**Target Platform**: Windows 10/11 & macOS 双端桌面运行 (Electron 壳 / Zero-Terminal Launch)  
**Project Type**: Desktop-first Web & Local Engine  
**Performance Goals**: 滤镜引入带来的压制性能开销 < 15%（实测 1080P 导出帧率维持在 70+ fps），单帧处理低至 14ms  
**Constraints**: 
- 零黑边污染：滤镜在 scale 后、pad 补黑边前执行，绝不让亮度提升将纯黑背景变灰。
- 色彩空间一致性：在 iPhone HDR HLG/Dolby Vision 色调映射到 BT.709 后再进入滤镜链。
- 色度通道保护：严禁在色度通道进行过度卷积，杜绝唇周泛紫泛绿等彩杂边。

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: C端体验与免终端启动**: 全流程通过工作台策略面板 UI 切换，完全图形化，错误与状态友好提示。通过。
- **Principle II: Harness 抽象与引擎解耦**: 滤镜处理属于底层音视频管线（Native Engine），上层 Harness 接口与 LLM 无耦合。通过。
- **Principle III: 智能音视频管线与声画解耦**: 严格遵循声画分轨原则，口播主音频 `-map 0:a` 或拼合音频完全不受视频滤镜影响，且与 B-roll 空镜及 ASS 字幕无缝合成。通过。
- **Principle IV: 硬件感知与批处理并发调度**: 实测滤镜链对 CPU 占用轻微，1080P 转码保持在 70+ fps，完全支持批处理流水线并发调度。通过。
- **Principle V: 极简高效与防无用循环**: 摒弃复杂的外部 AI 磨皮深度神经网络模型（需要数百兆权重且单帧推理数十毫秒），直接利用 FFmpeg 高度优化的多线程 C 语言原生微平滑与 CAS 滤镜，代码精简，短链路高可靠。通过。
- **Quality Gates: FFmpeg 指令结构化组装**: `build_portrait_filter_chain()` 函数进行强类型参数校验与线性衰减插值，严格保障指令格式与边界安全。通过。

---

## Project Structure

### Documentation (this feature)

```text
specs/010-portrait-filter-enhancement/
├── spec.md              # 需求规格与用户故事
├── checklists/
│   └── requirements.md  # 需求质量自检清单
├── research.md          # 行业调研、锐化结论与最佳参数矩阵
├── plan.md              # 架构设计与实现计划 (本文档)
├── data-model.md        # 实体扩展与滤镜参数模型
├── contracts/
│   └── filter_presets_api.json # 前后端交互 API 契约
└── quickstart.md        # 快速测试与效果验证指南
```

### Source Code Changes

```text
backend/
├── app/
│   ├── models/
│   │   └── entities.py              # [MODIFY] EditingStrategy 新增 filter_preset, filter_strength
│   ├── native_engine/
│   │   └── ffmpeg_filter.py         # [MODIFY] 新增 build_portrait_filter_chain(), 升级 build_color_normalize_filter() 与 compose_jl_cut()
│   └── api/
│       └── editor.py                # [MODIFY] 新增 GET /api/editor/filter-presets 预设清单接口
frontend/
└── src/
    └── components/
        └── editor/
            └── StrategySettings.tsx # [MODIFY] 策略抽屉新增“画面调优与口播滤镜”卡片 (4大预设切换 + 强度滑块)
tests/
└── test_portrait_filters.py        # [NEW] 滤镜预设、插值、黑边防污染及视频合成测试
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| *无宪章违规* | 严格遵守极简工程实践 | 不引入庞大的第三方人脸美颜 PyTorch/ONNX 库，使用原生 FFmpeg 算法链，实现轻量级 0 负担秒级渲染 |

---

## 阶段规划与后续执行路径 (Next Steps)

1. **Phase 1 设计已全部完成**：
   - 包含 spec.md, research.md, data-model.md, contracts/, quickstart.md, plan.md。
2. **Phase 2 任务拆解**：
   - 运行 `/speckit-tasks` 生成原子任务清单 `tasks.md`，随后进入自动化编码与验证。
