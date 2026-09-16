# Implementation Plan: 口播视频字幕增强与多剪辑策略组合实验 (003-subtitle-strategy-preview)

**Branch**: `003-subtitle-strategy-preview` | **Spec**: [spec.md](./spec.md)

---

## 1. 架构总览

```
[ 口播原视频 ]
      │
      ▼
[ ASR 识别 + 6~12字黄金断句 ]
      │
      ▼
[ Harness 上下文专有词纠偏 + 关键词特征标签提取 ]
      │
      ▼
[ 剪辑工程 CutProject (持有 EditingStrategy) ]
      │
      ├───────────────────────────────────────────┐
      ▼ (前端即时渲染)                              ▼ (后端物理压制)
[ Strategy Studio 策略控制面板 ]            [ FFmpeg 复合滤镜烧录 ]
  - 4种字幕色彩/字体主题                       - ASS 高级样式内联字幕 (高亮词独立变色)
  - 自动/手动关键词黄色高光                     - drawtext / overlay 顶部大标题横幅
  - 顶部挂顶 Title 标题横幅                    - 右上角半透明品牌水印角标
  - 品牌防搬运水印角标                         - J/L Cut 节奏空镜穿插
  - 空镜穿插节奏 (快剪/标准/纯口播)                  │
      │                                           ▼
      ▼                                  [ 最终高品质 MP4 视频 ]
[ 9:16 竖屏播放器实时所见即所得 ]
```

---

## 2. 详细变更清单

### 2.1 后端工程改造 (Backend)

1. **实体与模型扩展**：
   - [`backend/app/models/entities.py`](file:///d:/project/video_cut/backend/app/models/entities.py)：
     - 新增 `EditingStrategy` 类（定义字幕主题、字体大小、高亮开关及颜色、顶部横幅开关及文案、品牌水印开关及文案、空镜节奏）。
     - `CutProject` 增加 `strategy: EditingStrategy` 字段并赋予默认爆款配置。

2. **ASR 黄金断句切分器**：
   - [`backend/app/native_engine/asr_runner.py`](file:///d:/project/video_cut/backend/app/native_engine/asr_runner.py)：
     - 增加 `split_into_readable_segments()`，将 > 12 字的长难句按逗号或声学停顿安全拆分为 6~12 字的短促字幕片段，提升移动端完播视读率。

3. **策略持久化与热更新 API**：
   - [`backend/app/api/editor.py`](file:///d:/project/video_cut/backend/app/api/editor.py)：
     - 增加 `PUT /api/v1/projects/{project_id}/strategy` 端点，支持前端策略面板以及全局 Harness Copilot 抽屉随时更新工程的剪辑策略。

4. **FFmpeg 复合策略烧录器升级**：
   - [`backend/app/native_engine/subtitle_styler.py`](file:///d:/project/video_cut/backend/app/native_engine/subtitle_styler.py)：
     - 新增 `generate_ass_file()`，根据 `EditingStrategy` 输出带行内高亮颜色标签（`{\c&H00FFFF&}`、`{\b1}`）的 `.ass` 字幕。
   - [`backend/app/native_engine/ffmpeg_filter.py`](file:///d:/project/video_cut/backend/app/native_engine/ffmpeg_filter.py)：
     - 在 `compose_jl_cut()` 中复合烧录：如果开启了顶部横幅或水印，通过 FFmpeg 滤镜链叠加 `drawbox` + `drawtext`，压制出与播放器一模一样的成片。

---

### 2.2 前端工作台改造 (Frontend)

1. **剪辑策略组合面板 (Strategy Studio)**：
   - [`frontend/src/components/StrategyStudio.tsx`](file:///d:/project/video_cut/frontend/src/components/StrategyStudio.tsx) (新建组件)：
     - **字幕主题切换器**：4 种卡片预设（爆款金黄 / 科技翡翠 / 荧光记号 / 极简投影白），带微缩视觉样例图标。
     - **关键词高亮控制器**：高亮开关、颜色拾取器/预设调色盘（金黄/橙红/翠绿）、放大微效开关。
     - **顶部挂顶 Title 横幅设置**：开关、主标题输入框、副标题输入框、胶囊/通栏样式切换。
     - **品牌水印设置**：开关、水印文案输入框、透明度滑块。
     - **空镜穿插节奏**：快节奏卡点 (2s) / 标准教学 (3.5s) / 纯净口播 (无空镜)。

2. **竖屏播放器层级升级**：
   - [`frontend/src/components/VideoPlayer.tsx`](file:///d:/project/video_cut/frontend/src/components/VideoPlayer.tsx)：
     - 顶部渲染：挂顶大标题胶囊横幅（可带发光渐变背景与图标）。
     - 右上角渲染：品牌微透明水印角标。
     - 底部字幕渲染：基于 `strategy` 动态注入主题 CSS；自动扫描 `matched_keywords` 拆分出带特殊强调色和微放大的高亮文字。

3. **剪辑工作台整合**：
   - [`frontend/src/pages/VideoEditor.tsx`](file:///d:/project/video_cut/frontend/src/pages/VideoEditor.tsx)：
     - 右侧时间轴上方增加选项卡切换：【字幕与空镜轨道】 vs 【策略实验 (Strategy Studio)】。
     - 策略改动实时双向同步到播放器与后台工程。

---

## 3. 验证与测试计划

1. **单元与集成测试**：
   - 创建 `tests/test_subtitle_strategy.py`：
     - 测试 `split_into_readable_segments()` 确保无 > 12 字超长句。
     - 测试 `generate_ass_file()` 确保高亮词正确包含 ASS 变色标签。
     - 测试 `PUT /api/v1/projects/{id}/strategy` 正确更新与读取。
2. **全流程回归**：
   - 运行全量测试套件 `pytest`，确保原有 23 个测试及新特性测试全部通过。
   - `pnpm --prefix frontend run build` 确保 TypeScript 与前端打包 100% 成功。
3. **UI 实操验证**：
   - 启动服务后在浏览器打开工作台，切换 4 套策略方案，确认播放器预览与最终压制效果一致。