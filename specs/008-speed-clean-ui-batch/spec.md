# Feature Specification: 视频编辑倍速、Taste UI 极简去繁与批量混剪工作台重构 (008-speed-clean-ui-batch)

**Feature Branch**: `008-speed-clean-ui-batch`
**Created**: 2026-09-19
**Status**: Draft
**Input**: 用户指令：“然后选择一下视频可以编辑的倍速，新增加功能的话要考虑页面的美观，用一下taste skill https://github.com/Leonxlnx/taste-skill, 再考虑一下删除页面上无意义的模块，以及对功能无意义的解释，把这些删除掉，保持最清洁，功能完善的页面，批量混剪页面也要好好设计，你作为一个10年经验的页面设计专家和产品经理，再设计一下怎么表达效果是最好的”

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 视频剪辑变速与声画字幕等比自适应 (Priority: P1)
短视频创作者在剪辑工作台调整口播语速与节奏（如 1.0x 正常原速、1.1x 紧凑微快、1.15x 轻快顺畅、1.2x 节奏干脆、1.25x 极速快嘴）。系统在复合压制时利用 FFmpeg 进行高质量画面加速（`setpts`）与音频保调加速（`atempo`，杜绝变调花栗鼠声），并自动将所有字幕起止时间戳与空镜切入点等比缩放，确保声画、分镜和动态高亮字幕 100% 严丝合缝；同时播放器提供即时预览倍速切换。

- **Why this priority**: 口播短视频完播率与信息密度高度依赖语速把控。微加速（1.1x~1.2x）是行业公认的爆款标准操作。
- **Independent Test**: 选择 1.2x 倍速，执行合成后成片时长恰好缩短至原长约 83.3%，音频音调正常且字幕折行与高亮在加速后与真人发音时刻精确吻合。

### User Story 2 - Taste-Skill 反油腻极简去繁与界面净化 (Priority: P1)
遵循 `design-taste-frontend` 顶级审美标准，对剪辑工作台（VideoEditor）与策略工坊（StrategyStudio）进行彻底减法清理。删除所有无意义的自嗨解释文案、冗余括注说明、重复徽章与割裂卡片；统一为中性黑灰底色 + 单一高对比度主强调色（Indigo/Blue）；按钮标签单行克制，交互反馈精准干脆，重塑生产力工具的高级专业感。

- **Why this priority**: AI 生成界面往往充斥大量自述性碎碎念与花哨渐变，破坏专业工作流的沉浸感与效率。
- **Independent Test**: 审查页面 DOM 与文案，确认无任何多余的系统说明段落、无重复 CTA、无冗余括号注释，界面纯净通透，核心操作一步直达。

### User Story 3 - 10年资深专家级批量混剪工作台 (Priority: P1)
将批量混剪页面（BatchCut）重构为生产级“内容工厂驾驶舱”。将页面从单一上下堆叠改为“成片画廊（Gallery）与任务矩阵（Queue）”双模态设计。顶部紧凑常驻批处理参数（画幅、倍速、并发），右侧一键导入；主视觉默认聚焦于高质量成片卡片流（支持 Hover 视频预览、一键微调、目录唤起）；硬件占用收缩为极简胶囊状态，去除冗余的 4 块硬件仪表板。

- **Why this priority**: 批量混剪是创作者规模化生产的核心阵地，用户需要的是“一眼看到产出了哪些好视频”并快速交付，而非盯着无意义的 CPU 监控。
- **Independent Test**: 在新版批量混剪页面直接拖入多个视频并选择 1.1x 倍速启动，任务以高密度进度条呈现，完成后无缝加入成片画廊，直接点击卡片即可在弹窗极速预览高清成片。

---

## Technical Constraints & Boundaries
1. **FFmpeg 复合滤镜契约**:
   - 视频加速: `[v]setpts=(1/speed)*PTS[v_speed]`
   - 音频加速: `[a]atempo=speed[a_speed]`（保证音调 pitch 锁定）
   - 字幕时间伸缩: `new_start = round(start / speed, 3)`, `new_end = round(end / speed, 3)`
   - 空镜切点伸缩: `new_broll_start = round(start / speed, 3)`, `new_broll_end = round(end / speed, 3)`
2. **SQLite 权威持久化**:
   - `EditingStrategy.video_speed: float = 1.0` 存储于 `strategy` JSON 字段，默认 1.0。
3. **Taste-Skill 前端规范**:
   - 单一主题强调色，禁用多色渐变与 AI 紫。
   - 所有按钮文字单行，不折行。
   - 严格删除无实际功能说明的提示标签。