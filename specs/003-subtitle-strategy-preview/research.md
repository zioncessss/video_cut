# Phase 0: Research & Technology Decisions (003-subtitle-strategy-preview)

## 1. 口播视频 ASR 识别与断句最佳方案

- **调研问题**：口播短视频长难句较多，如何生成最适合短视频受众阅读的字幕？
- **业界方案对比**：
  1. *纯按标点断句*：ASR 识别结果常常 15~25 个字一句话，移动端竖屏要么字号极小，要么占满两三行，遮挡口播讲师面部，用户阅读阻力极大。
  2. *固定字符数截断*：容易在词汇中间劈开（例如将“科目二”劈为“科目”和“二”），造成阅读断层。
  3. *标点/逗号强断句 + 黄金字数意群拆分（选用方案）*：
     - 单屏字幕理想字数：**6 ~ 12 个汉字**（最长不超过 14 字）。
     - 切分逻辑：优先依据 ASR 的停顿静音切片，若一个分句超过 12 字，且包含专有名词或连词（如“今天带大家看看 / 我们自建的五万平标准化训练场”），结合时间跨度按比例线性插值拆分为两段短时字幕。
- **决定**：在 [`asr_runner.py`](file:///d:/project/video_cut/backend/app/native_engine/asr_runner.py) 中增加智能短句细分器 `split_into_readable_segments()`，确保单屏字幕不超过 12 字，视觉轻量呼吸感强。

---

## 2. 关键词高亮视觉实现方案 (Web 实时预览 vs FFmpeg 导出)

- **调研问题**：如何既能在前端播放器实现毫秒级预览，又能在后端 FFmpeg 导出中精确烧录高亮文字？
- **决定与架构方案**：
  - **前端预览 (Web Layer)**：
    - 利用正则扫描当前字幕中的 `matched_keywords`（如“五万平”、“科目二”、“倒库”）。
    - 将纯文本分割为普通文字与高亮文字 span：`<span class="text-white font-bold">{normal}</span><span class="text-amber-400 font-extrabold text-[1.1em] drop-shadow-md">{highlight}</span>`。
    - 纯 CSS / Tailwind 驱动，零延迟热切换颜色与阴影。
  - **后端压制 (FFmpeg Layer)**：
    - 方案 A (SRT)：标准 SRT 不支持部分文字局部变色或高级样式。
    - 方案 B (ASS 字幕 / Advanced SubStation Alpha，选用方案)：ASS 字幕支持内联标签，如 `{\c&H00FFFF&}`、`{\b1}`，可以精确对单句话中的某个词赋予独立颜色和字号，并通过 `ffmpeg -vf "ass=output.ass"` 或 `subtitles` 滤镜烧录。
    - 方案 C (Drawtext 滤镜复合)：用于顶部挂顶 Title 横幅和右上角水印角标的压制。

---

## 3. 剪辑策略与视觉模版预设 (Composable Strategy Matrix)

借鉴“爱拍”、“剪映”的预设方案机制，将策略拆分为 4 个正交可自由组合的维度：

1. **Theme (字幕字体与色彩主题)**：
   - `viral_gold` (爆款金黄)：深色描边黑底胶囊 + 重点词高亮发光金黄（#FACC15）
   - `tech_emerald` (科技翡翠)：毛玻璃暗灰底 + 纯白文字 + 重点词科技青绿（#10B981）
   - `marker_pen` (教学荧光)：底色微透明 + 重点词带有鲜明荧光黄衬底（#FEF08A）
   - `minimal_white` (纯净投影)：无底框 + 纯白特粗字体 + 3px 柔和立体阴影
2. **Highlighting (高亮策略)**：
   - `keyword_auto` (自动提取驾校核心词)
   - `color_scheme` (黄色 / 橙色 / 翠绿 / 荧光粉)
   - `scale_up` (高亮词轻微放大 1.1x)
3. **Banner & Watermark (挂顶标题与品牌水印)**：
   - `show_top_banner`: 是否开启顶部挂顶横幅（支持自定义主标题与副标题，如“🔥 考驾照必看”）
   - `banner_style`: 胶囊圆角 (Capsule) / 全屏通栏 (Full Width)
   - `show_watermark`: 是否开启右上角品牌角标（支持自定义文字，如“XX驾校官方教学”）
4. **B-roll Pacing (空镜穿插节奏策略)**：
   - `fast` (快节奏混剪，2s 一切)
   - `standard` (标准教学，3-4s 一切)
   - `talking_only` (纯口播，无空镜)