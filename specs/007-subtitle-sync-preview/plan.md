# Implementation Plan: 字幕实时保存与成片预览所见即所得同步 (007-subtitle-sync-preview)

**Branch**: `007-subtitle-sync-preview` | **Date**: 2026-09-19 | **Spec**: [specs/007-subtitle-sync-preview/spec.md](file:///d:/project/video_cut/specs/007-subtitle-sync-preview/spec.md)

**Input**: Feature specification from `specs/007-subtitle-sync-preview/spec.md`

## Summary

解决用户在字幕列表中修改字幕后“未感觉实时保存”、“生成预览未按修改更新”以及“实时预览字体与生成预览字体大小不同步”三个核心痛点。方案通过：
1. **前端字幕状态管理不可变性重构与状态可视化**：为字幕列表添加失焦即存（Blur Flush）、回车确认、不可变克隆与 `● 正在保存...` / `✓ 已同步` 状态 Badge；
2. **渲染前强制同步与时间戳防缓存机制**：在 `handleRender` 前置取消未完成防抖，链式等待最新字幕与策略写入权威 SQLite，渲染完成附带唯一时间戳通知 `<video>` 彻底刷新；
3. **物理视频有效视口（Active Viewport）与 1:1 等比字号模型**：在播放器中排除外围 Letterbox/Pillarbox 黑边，严格按视频实际物理画面尺寸计算 `scaleFactor = videoH / 1920`，使 DOM 虚拟字幕与 FFmpeg ASS 压制成片达到像素级绝对一致。

## Technical Context

**Language/Version**: TypeScript 5.2 / React 18 (前端), Python 3.11 (后端)  
**Primary Dependencies**: React, TailwindCSS, Lucide-react, Axios, FastAPI, Pydantic v2, FFmpeg / libass  
**Storage**: 本地 SQLite 3 (`storage/videocut.db`) 为唯一权威数据源  
**Testing**: `pytest` (后端单元与集成测试), `pnpm build` (前端类型与构建验证)  
**Target Platform**: Windows 10/11 & macOS 桌面环境 (Electron / Chrome 运行时)  
**Project Type**: 桌面端 Web / Electron 视频创作工作台  
**Performance Goals**: 字幕输入响应 <16ms (60fps)，失焦落盘延迟 <150ms，DOM 与 ASS 字号误差 <2%  
**Constraints**: 严格遵循单一权威 SQLite 库准则；不得破坏已有分镜决策与素材编排结构；凭据安全红线  
**Scale/Scope**: 单个视频工程 20~200 条字幕，单视频播放器分辨率 1080x1920  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: C端体验与免终端启动** → **PASS**: 全部状态转换（保存中、已保存、错误）通过浅色质感界面 Badge 呈现，操作友好透明。
- **Principle II: Harness 抽象与引擎解耦** → **PASS**: 本次改动聚焦于字幕编辑持久化与播放器排版渲染，不侵入底层 Harness Adapter 接口。
- **Principle III: 智能音视频管线与声画解耦** → **PASS**: 严格保障字幕修改后，ASS 压制成片与实时编辑界面的声画同步与排版所见即所得。
- **Principle IV: 硬件感知与批处理并发调度** → **PASS**: 强化了渲染前的数据校验与句柄清理，消除因同名视频并发读写锁定的文件冲突。
- **Principle V: 极简高效与防无用循环** → **PASS**: 使用标准的不可变更新与简单的 Ref 缓存，不引入庞大的全局状态管理库，拒绝过度工程。

## Project Structure

### Documentation (this feature)

```text
specs/007-subtitle-sync-preview/
├── spec.md              # 需求规格说明书
├── plan.md              # 本技术实现方案
├── research.md          # Phase 0 调研与技术决策报告
├── data-model.md        # Phase 1 实体与状态模型
├── quickstart.md        # Phase 1 验证指南
├── contracts/           # Phase 1 契约定义
│   └── api-endpoints.md # Web API 与组件 Props 契约
└── checklists/
    └── requirements.md  # 质量验证清单
```

### Source Code (affected components)

```text
frontend/src/
├── pages/
│   └── VideoEditor.tsx              # 改造 handleTextChange、渲染前置同步刷新与防缓存重载
└── components/
    ├── SubtitleList.tsx             # 增补保存状态 Badge、onBlur/Enter 提交回调
    ├── VideoPlayer.tsx              # 引入 Active Video Viewport 测量与 scaleFactor 精准映射
    └── StrategyStudio.tsx           # 字号滑块与预设联动逻辑核验

backend/app/
├── api/
│   └── editor.py                    # 验证 update_subtitles 事务落库与 render_project 稳定性
└── native_engine/
    └── subtitle_styler.py           # 核验 ASS 样式与 CSS 样式字号、边距参数对齐

tests/
└── test_subtitle_sync_and_styler.py # 后端接口与 ASS 字号样式对应关系测试
```

## Implementation Phases

### Phase 0: Outline & Research (Completed)
- 详见 [research.md](file:///d:/project/video_cut/specs/007-subtitle-sync-preview/research.md)
- 确定不可变更新 + 三重提交（防抖、失焦、渲染前置强制刷新）架构；
- 确立物理视频有效视口几何测算与 `scaleFactor = videoH / 1920` 绝对等比公式。

### Phase 1: Design & Contracts (Completed)
- 详见 [data-model.md](file:///d:/project/video_cut/specs/007-subtitle-sync-preview/data-model.md) 与 [contracts/api-endpoints.md](file:///d:/project/video_cut/specs/007-subtitle-sync-preview/contracts/api-endpoints.md)；
- 更新 `AGENTS.md` 上下文指向本 plan.md。

### Phase 2: Implementation Steps (To be executed via `/speckit-tasks` & `/speckit-implement`)
1. **字幕列表不可变性与状态指示增强**：
   - 优化 `SubtitleList.tsx`，在标题栏增加状态徽章（`全部已同步` / `保存中...` / `已保存`）；
   - 在 `textarea` 上增加 `onBlur` 与 `onKeyDown` 快捷提交触发。
2. **VideoEditor 保存与渲染前置同步**：
   - 修复 `handleTextChange` 中的原地属性修改，改为不可变对象 map；
   - 引入 `latestSubtitlesRef` 与 `flushPendingSubtitles`，在 `handleRender` 中强制同步落盘确认后再触发渲染；
   - 强化成片模式视频重载（带有 `?t=${Date.now()}` 破除浏览器缓存），并在成片模式下编辑字幕时给予清晰指引。
3. **VideoPlayer 物理视频视口与等比字号对齐**：
   - 测量容器宽高与视频实际渲染宽高（自动识别 Letterbox/Pillarbox 黑边）；
   - 建立内部 `Active Viewport Layer`，所有字幕、横幅、水印、手柄均以实际视频画面为 100% 坐标基准；
   - 统一字号缩放比例公式：`Math.round(fontSizeBase * (videoH / 1920))`，与 ASS `PlayResY: 1920` 完全对称。
4. **自动化测试与全链路验证**：
   - 编写 `tests/test_subtitle_sync_and_styler.py` 验证字幕落库与 ASS 生成一致性；
   - 执行 `pnpm build` 确认前端无类型或打包错误。
