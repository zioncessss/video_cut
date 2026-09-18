# Phase 0 Research: 字幕实时保存、成片预览同步与字号排版对齐

**Feature**: `007-subtitle-sync-preview`  
**Date**: 2026-09-19  

## Research Topics & Decisions

### 1. 字幕即时持久化与编辑状态管理 (Subtitle Real-Time Persistence & Dirty State)

#### Problem
在当前实现中，用户在 `SubtitleList.tsx` 中编辑字幕或调整高亮词时存在以下问题：
1. **原地属性修改破坏 React 响应性**：`handleTextChange` 执行 `const updated = [...subtitles]; updated[idx].corrected_text = newText;`，数组虽浅拷贝但项对象未拷贝，导致引用未变，子组件浅比较可能跳过更新。
2. **缺乏即时保存与明确状态反馈**：仅依赖 500ms 防抖；用户在修改后看不到任何“保存中”或“已保存”反馈，心理感觉“好像没有实时保存”。
3. **失焦与回车未立即 Commit**：用户输入完毕后立即点击外部操作（如生成预览或切换选项卡），如果防抖计时器未到，修改可能滞留在前端内存中未写入 SQLite。

#### Decision & Architecture
- **不可变数据更新**：
  在 `handleTextChange` 中使用 `setSubtitles(prev => prev.map((s, i) => i === idx ? { ...s, corrected_text: newText, is_manual_edited: true } : s))`。
- **三重提交保障机制**：
  1. **防抖持久化**：用户持续输入时，保留 500ms 防抖自动提交；
  2. **失焦/回车即时提交 (Immediate Flush on Blur/Enter)**：`onBlur` 与 `onKeyDown(Enter)` 立即触发即时保存，清空防抖定时器；
  3. **强制刷新引用 (`flushPendingSubtitles`)**：通过 `latestSubtitlesRef` 维护最新字幕引用，外部操作（如点击生成预览）可直接获取最新数据并强制同步。
- **可视化保存状态指示**：
  在字幕列表顶部增加统一状态 Badge：
  - `IDLE`: `✓ 全部已同步`（文字浅灰）
  - `SAVING`: `● 正在保存至本地库...`（蓝色微动动效）
  - `SAVED`: `✓ 已保存 (刚刚)`（绿色微标，3秒后渐隐转 IDLE）
  - `ERROR`: `✕ 保存失败，点击重试`（红色高亮并支持手动重试）

---

### 2. 生成预览前强制同步与防视频缓存 (Render Pre-flush & Video Cache Invalidation)

#### Problem
1. **渲染与保存竞态**：点击“生成预览”时，若上一句字幕刚输入完毕尚未触发防抖，前端可能向 `/render` 触发了旧数据，或并发的 `/subtitles` 与 `/render` 在后端产生时序倒挂。
2. **浏览器媒体文件缓存停滞**：后端生成的视频路径虽然带有时间戳，但前端播放器在切换 `rendered` 模式时，如果 `<video>` 标签没有被强制刷新或 URL 参数未被识别，浏览器会复用上一版成片的解码缓存，导致画面未更新。
3. **模式认知脱节**：用户在播放“已压制成片”（burnt-in MP4）时在右侧修改了字幕，此时播放器展示的是已压制进视频画面的旧字幕，用户会困惑“为什么我改了没变”。

#### Decision & Architecture
- **生成预览前置同步守卫 (`handleRender`)**：
  1. 立即清除所有等待中的防抖定时器；
  2. 使用 `latestSubtitlesRef.current` 和 `latestStrategyRef.current` 依次同步 `PUT /projects/{id}/subtitles` 和 `PUT /projects/{id}/strategy`，等待 `Promise.all` 或链式落盘成功；
  3. 携带落盘确认后再发起 `POST /projects/{id}/render`。
- **强制破除浏览器视频缓存**：
  - `outputVideoUrl` 绑定响应式 `outputTimestamp`，播放器传入 `src={`${mediaUrl}?t=${outputTimestamp}`}`；
  - 渲染完成后在 `VideoPlayer` 中主动调用 `videoRef.current.load()` 重新拉取新媒体源流，杜绝复用陈旧解码器缓存。
- **成片模式与交互模式状态解耦**：
  - 当处于 `previewMode === 'rendered'` 状态时，一旦用户在右侧编辑了任何字幕或样式，播放器顶部提示栏以醒目的琥珀色徽章提示：`“已修改字幕，当前呈现上一版成片，点击【重新合成】查看新成片”`，并提供一键返回实时编辑模式的入口；
  - 实时编辑模式（`previewMode === 'interactive'`）立即以 DOM 虚拟图层呈现最新修改，提供零延迟直观预览。

---

### 3. 交互编辑器与压制成片 1:1 所见即所得 (WYSIWYG Overlay Parity)

#### Problem
1. **外层黑边容器导致缩放因子严重失真**：
   - 当前 `VideoPlayer.tsx` 的 `scaleFactor` 计算方式为 `containerWidth / 1080`；
   - 播放器外层容器 `containerRef` 受弹性布局高度约束，当窗口宽高比偏宽或偏高时，容器内产生上下或左右的 Letterbox / Pillarbox 黑色留白；
   - `<video>` 采用 `object-contain` 居中显示，其实际像素宽高度远小于 `containerRef.clientWidth`（例如容器宽 420px，但 9:16 视频实际仅宽 280px）；
   - 导致 DOM 字幕的字号按 420px 放大了 1.5 倍，而压制成片实际在 280px 的画面中渲染，造成“实时编辑字号巨大、生成预览字号过小”的严重脱节。
2. **字幕宽度百分比基准错位引发折行不一致**：
   - 实时预览中字幕框宽度设为 `width: 90%`（相当于容器宽度的 90%，跨入了黑边区域）；
   - ASS 压制成片中 `margin_h = int(1080 * (100 - 90) / 200) = 54px`（严格基于 1080 视频画面的 90%）；
   - 导致在预览中一整行能容纳的文本，压制到成片中被强制换行成了两行。

#### Mathematical Derivation & Solution
- **物理视频视口（Active Video Frame Viewport）测量**：
  定义容器宽高 `cw, ch`，视频逻辑宽高比 `ar`（竖屏 9/16 = 0.5625，横屏 16/9 = 1.7778）：
  ```ts
  const containerAspect = cw / ch;
  let videoW = cw;
  let videoH = ch;
  let videoLeft = 0;
  let videoTop = 0;

  if (containerAspect > ar) {
    // 容器更宽：高度撑满，左右黑边 (Pillarbox)
    videoH = ch;
    videoW = ch * ar;
    videoLeft = (cw - videoW) / 2;
    videoTop = 0;
  } else {
    // 容器更高：宽度撑满，上下黑边 (Letterbox)
    videoW = cw;
    videoH = cw / ar;
    videoLeft = 0;
    videoTop = (ch - videoH) / 2;
  }
  ```
- **专用等比视口容器 (Active Viewport Layer)**：
  在 `<video>` 之上构建与实际视频完全重合的专用定位容器：
  ```tsx
  <div
    style={{
      position: 'absolute',
      left: `${videoLeft}px`,
      top: `${videoTop}px`,
      width: `${videoW}px`,
      height: `${videoH}px`,
      pointerEvents: 'none',
    }}
  >
    {/* 所有字幕、横幅、水印、高亮以及拖拽手柄均置于此视口中 */}
  </div>
  ```
- **绝对等比字号映射公式**：
  - ASS 压制逻辑：`PlayResY: 1920`，字号 `chosen_font_size`（如 72）；即字高占画面高度的 `72 / 1920 = 3.75%`。
  - CSS 虚拟字幕字号：
    ```ts
    const scaleFactor = videoH / 1920;
    const subtitlePx = Math.max(10, Math.round(subtitleFontSizeBase * scaleFactor));
    ```
  - 同理，横幅字号：`bannerTitlePx = Math.round(bannerFontSizeBase * scaleFactor)`。
  - 水印字号：`wmPx = Math.round(wmFontSizeBase * scaleFactor)`。
- **宽度百分比与换行对齐**：
  由于视口容器宽度即为 `videoW`，`subtitle_width_percent = 90` 即代表实际画面宽度的 90%，与 ASS 的 `margin_h` 100% 几何对称，彻底消灭折行差异。
- **字体与渲染平滑**：
  统一前端预览字体为 `fontFamily: '"Microsoft YaHei", sans-serif'`，匹配 ASS 的 `Style: Default,Microsoft YaHei`。
