# Implementation Plan: 015-text-behind-person-cover (人后拱形 3D 穿插爆款封面模板与 Canvas 分层渲染体系)

**Branch**: `015-text-behind-person-cover` | **Date**: 2026-09-24 | **Spec**: [specs/015-text-behind-person-cover/spec.md](file:///d:/project/video_cut/specs/015-text-behind-person-cover/spec.md)

**Input**: 用户的爆款同城 IP 封面复刻需求，已下载并深度解构 GitHub 5k+ ⭐ 开源项目（`RexanWONG/text-behind-image`），确立“直接复用三层 Canvas 时序 + 本地离线抠图供给 + 彩虹拱形逐字贴纸增强”的完整技术方案。

---

## 1. 总体目标与复用边界 (Summary & Reuse Boundaries)

### 1.1 核心交付目标
1. **纯前端 Canvas 分层渲染（60fps 实时）**：
   - `Layer 0 (底层)`: 视频原始帧画面铺底。
   - `Layer 1 (人后文字)`: “杭州学车”大字以单字独立起伏气泡贴纸沿彩虹拱形弧度展开，自然穿插在人物脑后。
   - `Layer 2 (置顶人像)`: 抠出的透明背景人物图层，带 8~14px 纯白贴纸发光外边覆盖在大字上方。
   - `Layer 3 (转化层)`: 胸前“避坑课”斜角卡片 + 底部高饱和柠檬黄（#FFEE0A）转化大字。
2. **端到端离线协同**：截帧时自动生成透明人像图层，前端无感直接渲染，完全摆脱对外部几十兆大模型下载的依赖。
3. **导出像素级 1:1 对齐**：后端 `cover_generator.py` 同步扩展该模板渲染分支，保证成片第一帧与封面图片导出 100% 镜像一致。

### 1.2 GitHub 开源项目 (`RexanWONG/text-behind-image`) 复用与改造清单

```
本地源码参考路径: specs/015-text-behind-person-cover/vendor_reference/package/
├── dist/index.js               --> [直接复用] Canvas 三层绘制时序与异步生命周期
├── dist/backgroundRemoval.js    --> [直接复用] Canvas 原生 globalCompositeOperation 蒙版通道切割
└── dist/textRendering.js        --> [核心改造] 从死板线性横排升级为彩虹拱形自适应排列 + 逐字起伏描边
```

- **【100% 直接复用】**：
  - Canvas 三层绘制时序机制（底图 → 中层文本 → 顶层人像）。
  - 原生 `ctx.globalCompositeOperation = 'destination-in'` 高性能透明蒙版混合。
  - 文字阴影、旋转、对齐控制参数规范。
- **【本项目深度改造】**：
  - **抠图供给改造**：将浏览器前端耗时下载 `@imgly/background-removal` 模型的脆弱链路，替换为后端离线 0.8s 自动切分产出透明人像 PNG，前端直接按 URL 加载，0 失败率、0 流量浪费。
  - **拱形排版改造**：抛弃原项目的水平等距递增，采用正弦/抛物线高程计算与两端外倾旋转角，实现完美包围发顶。
  - **描边质感改造**：从单层平整 stroke 升级为逐字双层形态学膨胀贴纸，保留汉字笔画起伏小山丘。
  - **人像白光增强**：增加 `ctx.shadowColor = '#FFFFFF'; ctx.shadowBlur = 12` 贴纸白光渲染。
  - **四层转化信息增强**：扩充斜角卡片与底部柠檬黄大字。

---

## 2. Technical Context

**Language/Version**: TypeScript 5.2 (React 18 前端) / Python 3.12 (后端)  
**Primary Dependencies**: HTML5 Canvas API, Lucide React, FastAPI, Pillow 12, OpenCV  
**Storage**: SQLite 权威库 `storage/videocut.db`，封面候选图存储于 `storage/covers/candidates/`  
**Testing**: pytest (后端集成与单元测试), Vite 浏览器端到端实时验证  
**Target Platform**: Windows 11 Desktop (Electron + Web UI)  
**Project Type**: Web Application + Desktop Hybrid  
**Performance Goals**: 前端 Canvas 交互微调 60fps 实时渲染，抽帧人像图层生成 < 1 秒  
**Constraints**: 0 外部网络下载依赖（纯本地离线可用），100% 兼容存量工程与原有 6 大封面模板  

---

## 3. Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章核心原则 | 检验结论 | 说明 |
| :--- | :--- | :--- |
| **I. C端体验与免终端启动 (Zero-Terminal Launch)** | **PASS** | 全图形化拖拽交互，用户在封面面板一键选择模板，无需任何终端操作。 |
| **II. Harness 抽象与引擎解耦** | **PASS** | 封面设计属于 Native Engine 视觉层，不侵入大模型纠错与 Tier B 调度链路。 |
| **III. 智能音视频管线与声画解耦** | **PASS** | 封面作为独立视觉资产和视频首帧嵌入项，遵循声画可逆与可微调规范。 |
| **IV. 硬件感知与批处理并发调度** | **PASS** | 前端 Canvas 承担 90% 的即时微调算力，后端合成采用低内存流式渲染，不阻塞批处理队列。 |
| **V. 极简高效与防无用循环** | **PASS** | 严禁多层冗余轮询，透明图层生成采用精准单次派生与磁盘按需缓存。 |

---

## 4. 详细实施步骤拆解 (Execution Steps)

### 阶段一：前端 Canvas 分层渲染与拱形逐字算法接入 (`CoverPreviewSelector.tsx`)
1. **模板目录注册**：在 `FALLBACK_TEMPLATES` 中注册 `text_behind_person`（人后拱形字 · 3D穿插爆款），默认关联 `classic_blue`。
2. **三层绘制时序移植**：
   - 提取底图 `bgImage` 并铺底绘制。
   - 调用拱形逐字贴纸渲染器绘制中层文字。
   - 若存在透明人像 `personImage`，使用白光阴影预渲染人像描边，并覆盖人像本体。
   - 绘制 Layer 3 前景转化层（“避坑课”便签 + 底部“2980全公开”）。
3. **彩虹拱形逐字算法实现**：
   - 针对 4~5 字主标，计算各字符的 X 轴弧度分布、Y 轴抛物线抬升以及向外偏转的角度 $\theta_i$。
   - 单字双层描边（宝蓝内边 + 纯白外边），随笔画边缘凹凸起伏，单字间保留呼吸缝隙。

### 阶段二：人像透明图层端到端数据打通 (`api/editor.py` & `api.ts`)
1. **抽帧响应扩充**：在 `/projects/{id}/cover-candidates` 与 `/projects/{id}/cover-frame` 接口中，返回对应帧的 `person_thumb_url`。
2. **前端异步预载**：前端获取候选帧或选择时间戳后，预载 `person_thumb_url` 图像为 `HTMLImageElement`，载入完成后触发 Canvas 瞬时重绘。
3. **无缝降级保护**：若所选帧无人物或人像加载失败，Canvas 优雅呈现完整拱形文字，绝不报红崩溃。

### 阶段三：后端印刷级合成与第一帧导出对齐 (`core/cover_generator.py`)
1. **增加模板分支**：在 `render_cover_image` 中增加 `text_behind_person` 分支。
2. **像素级对齐验证**：保证 Pillow 导出的 1080×1920 高清大图与前端 Canvas 预览具有完全一致的字号比例、拱形曲率、描边厚度和色值。

### 阶段四：自动化测试与真机验收
1. 编写 `tests/test_cover_generator.py` 中的 `test_text_behind_person_render` 单测。
2. 端到端启动前端界面，进行真实视频候选帧的实时拖拽与导出成片验证。
