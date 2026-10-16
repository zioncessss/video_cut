# Research & Technical Decisions: 自主分镜切入裁剪与字幕重叠定位原口播视频误读裁剪 (Storyboard Trim & Subtitle Retake Pruning)

**Feature Branch**: `016-storyboard-trim-sub-retake-prune`
**Date**: 2026-10-14

## Research Summary

本文档针对口播短视频剪辑中“口误重读精准切除”、“分镜 In/Out 点自主截取覆盖”以及“播放器毫秒级实时所见即所得 (Live WYSIWYG)”三大核心技术挑战进行深度调研与方案选型。

---

## 1. 口误读错重读 (Voice Retake) 识别与防误剪算法

### 核心病灶与技术方案
1. **病灶 A：ASR 阶段短句过早粘连**
   - **现状**：`backend/app/native_engine/asr_runner.py:merge_short_segments` 会对停顿小于 0.55s 的相邻短句执行合并。若创作者说“顺达...”（停顿 0.4s）“顺达驾校自建训练场”，两句在 ASR 层被粘连为单句，导致下游粗剪完全检测不到口误。
   - **决策**：在 `merge_short_segments` 中引入**重读阻断守卫 (Retake Guard)**：若 `next_seg.text` 的前缀与当前短句 `cur_seg.text` 存在重叠（如前 2~3 个汉字相同），强制禁止合并，保持切片独立。
2. **病灶 B：全句 SequenceMatcher 相似度被稀释**
   - **现状**：`prune_engine.py:find_repeated_takes` 使用 `SequenceMatcher(None, s1, s2).ratio() > 0.6`。当误读句仅 4 个字，而正确重录句有 20 个字时，全局 ratio 仅 0.33，直接被漏判。
   - **决策**：采用**前缀重叠比对算法 (Prefix Overlap Ratio)**：
     截取 `prefix_len = len(cur_text)`，比对 `cur_text` 与 `next_text[:prefix_len]` 的相似度；若相似度 $\ge 0.75$ 且两句间停顿在 $0.2s \sim 1.8s$ 之间，高置信判定为口误重读。
3. **防误剪安全网 (Triple Safety Guard)**：
   - **排比连读保护**：两句停顿极短（$< 0.20s$）且语速连贯时判定为修辞排比，禁止误剪。
   - **长句完整语义保护**：前句字数 $\ge 9$ 且并非后句纯子串时，视为完整独立语意，禁止误剪。
   - **极短口误平滑保护**：对 $<0.3s$ 的极短口误，切点扩展 50ms 安全缓冲区，并在切口注入 15ms `afade` 交叉淡化，彻底杜绝爆音。

---

## 2. 原视频音画物理裁剪机制 (Physical Video/Audio Pruning)

### 决策与链路
- **严禁只删字幕**：字幕被删除后，必须同时在工程 `prune_spans` / `kept_spans` 中记录时间区间。
- **底层裁剪合成**：
  在 `backend/app/native_engine/ffmpeg_filter.py` 中，使用成熟的保留区间切片流水线：
  ```text
  [0:v]trim=start=s0:end=e0,setpts=PTS-STARTPTS[v0];
  [0:a]atrim=start=s0:end=e0,asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:d=0.015[a0];
  ...
  [v0][a0][v1][a1]...concat=n=K:v=1:a=1[outv][outa]
  ```
- **时间轴向左平移一致性**：
  若在 $T_1 \sim T_2$ 裁剪了时长 $\Delta = T_2 - T_1$，则所有位于 $T \ge T_2$ 的字幕项与分镜覆盖区间，其起始与结束时间统一向左平移 $\Delta$；若分镜区间恰好落在 $T_1 \sim T_2$ 内部，自动清除或缩小该分镜。

---

## 3. 分镜 In/Out 点截取与切入覆盖 (B-roll In/Out Trimming)

### 决策与模型
- **模型扩展**：`BrollReplacement` 新增 `source_start_time: float = 0.0`。
  - `target_start_time`: 主口播视频切入开始时间。
  - `target_end_time`: 主口播视频切入结束时间（时长 $\text{dur} = \text{target\_end} - \text{target\_start}$）。
  - `source_start_time`: 分镜素材选取的开始时间（默认为 0.0）。
  - `source_end_time`: 自动等于 `source_start_time + dur`，界面支持滑动或数字调节。
- **音频策略（基于 clarify 决策）**：
  分镜素材一律强制静音剥离音频，口播视频音频作为连续旁白持续输出，FFmpeg 仅对视频流执行 overlay/scale 处理。

---

## 4. 实时所见即所得 (Live WYSIWYG) 预览架构

### 前端虚拟时间轴 (Virtual Timeline Player)
- **零等待响应**：无需将调整后的片段重新发送给后端压制成临时 mp4 才能预览。
- **虚拟跳播 (Virtual Jump-Cut)**：
  前端监听 `video.ontimeupdate`，一旦进入被剪裁区间 $[t_{start}, t_{end}]$，立即执行 `video.currentTime = t_{end}`，实现零卡顿瞬时跳播。
- **分镜实时贴片 (Live B-roll Picture Overlay)**：
  在主播放器视频标签上方放置一个轻量级的绝对定位 `<video muted playsinline>`。当主视频进入分镜区间时，贴片视频按计算偏移同步播放，离开区间时自动隐藏，延迟 $< 30ms$。
- **卡片折叠与恢复**：
  被剔除卡片在 UI 上折叠为浅灰条，点击“恢复”时重新插回字幕数组并还原时间轴，纯前端状态变更，体验丝滑。
