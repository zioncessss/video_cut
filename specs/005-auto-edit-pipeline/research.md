# Research & Decisions: 005-auto-edit-pipeline

**Date**: 2026-09-17 | **Branch**: `005-auto-edit-pipeline`

## R1. AI 能否可靠判定高亮重点词？（用户核心疑问）

**Decision**: 能。采用「词库确定性命中 ∪ AI 判定 ∪ 手动编辑」三源合并，词库兜底、AI 增益。

**Rationale（实测证据，2026-09-17 真实调用）**:
- 提示词：现行 `prompting.build_correction_prompt()`（已要求每句输出 1~2 个 `highlight_keywords`）。
- 样本：12 句驾校口播（含「从今年九月份开始湖州驾校」「自建五万平训练场」「提检拍照一站式搞定」等）。
- 直连 API（设置页 glm-5.3-flash，bigmodel 端点）：17.8s 返回**完美 JSON**；
  - 纠偏：唯一错字「提检→体检」被正确识别（词库映射）；
  - 高亮：「九月份」「湖州驾校」「五万平」「一把过」「零基础」「包过」「杭州萧山」——时间/地点/数字/卖点全覆盖，无噪声词；
  - 「点红心关注教练」给出「点红心」「关注」，合理（行动号召也可视觉强调）。
- 结论：glm-5.3-flash 对此类短文本结构化任务判定质量高、无幻觉词；词库无法覆盖「九月份」「大改革」这类自由表达，AI 恰好补位。两者并集是最优解。

**Alternatives considered**:
- 纯词库高亮：维护成本高、覆盖不了自由表达（已否决，但保留词库做零延迟兜底与降级路径）。
- 纯 AI 高亮：AI 失败时无兜底，违反真实执行铁律的降级诚实性（否决）。

## R2. 分镜决策（场景切分 + 转场）AI 输出与效率

**Decision**: 新增独立「分镜决策」AI 调用（纠偏完成后第二步），输出严格 JSON；初版空镜素材按分类随机选取；转场时长由 AI 逐处决策（0.3~0.5s 约束），无转场能力时退化为硬切。

**实测数据（12 句样本，同一份新决策提示词）**:

| 链路 | 结果 | 耗时 | 备注 |
|---|---|---|---|
| 直连 API `/chat/completions`（非流式, timeout=60s） | **失败（超时）** | 60.3s | 正文生成过长触发超时；随后 `/responses` 备用端点在 bigmodel 返回 404，白白再等一轮 |
| codex 本地代理（`127.0.0.1:15721`） | **成功，JSON 质量优秀** | 112.3s | 决策完全符合预期：venue↔训练场、experience↔提检拍照、lesson↔教学练车；「不收燃油费」「点红心关注」「杭州萧山(仅客源地)」正确判 null 并给出理由 |

**效率设计对策（写入计划）**:
1. 决策调用 timeout 放宽至 **120s** 且批量场景天然并行（每视频一次决策调用，互不阻塞）；
2. `llm_client` 备用 `/responses` 端点仅对本地 codex 代理启用（远端供应商 404 纯浪费，改为按 provider 来源判定）；
3. 决策结果随工程持久化，重开工程/重新渲染不重复调用（只有 force 重跑或用户手动触发才重算）;
4. 输入上下文纪律维持精简（id+text+起止秒），输出约束 1~2 词理由，控制生成 token 数；
5. Tier B（codex/zcode CLI）可作为决策调用的备用链路，但作为后台批量路径而非交互阻塞路径。

**Alternatives considered**:
- 与纠偏合并成一次调用：耦合两种任务格式，纠偏失败会连坐决策；且决策依赖纠偏后文本（否决）。
- 本地规则引擎替代 AI：现有关键词匹配已是规则版，升级为 AI 正是本特性目标（保留为降级路径）。

## R3. 体验空镜（原体检空镜）语义归类

**Decision**: `medical → experience` 更名，语义定义为「学员用户体验流程类空镜」：报名咨询、体检、拍照、面签、上车初体验、模拟考试、拿证庆祝等以「人」为主体的流程画面。

**Rationale**: 驾校短视频叙事=环境（venue）/人（experience）/教学动作（lesson）三分；「体检」本质是报名体验流程的一环，归入 experience 语义最自然且向前后流程可扩展。客户语义未定时，触发词全部走 glossary.json `keywords.experience`，随时可改、立即生效（词库唯一事实源原则）。若客户未来给出全新定义，仅需改词库触发词与素材归类，不改代码。

**Alternatives considered**: 保留 medical 键仅改显示名（DB 与代码语义漂移，违反可读性原则；数据量尚小，正是迁移窗口）。

## R4. 转场技术方案

**Decision**: 分两档——P1 交付「精确硬切」（现管线 trim+concat 已满足「只切画面不动音轨」），P1.5 增加可选「0.3~0.5s 叠化」：相邻片段间用 `xfade=transition=fade:duration=D` 串联；音频整体取口播原轨不受影响。

**Rationale**: 现行 `compose_jl_cut` 的 trim→concat 管线音频 `map 0:a` 与口播完全对齐，天然满足 IR4；xfade 需要重排滤镜链（每处转场串联 offset 计算），作为增强而非阻塞项。AI 决策的 transition 字段两档通用（硬切时忽略）。

## R5. 高亮词时间轴可视化

**Decision**: 在「字幕与时间轴轨道」列表每句下方渲染高亮词 chip 标签（词库/AI/手动来源徽标 + 删除 ×），句内提供添加输入框；数据结构 `SubtitleSegment.highlight_words: List[HighlightWord{word, source}]`，渲染端（subtitle_styler）按 word 列表做行内 ASS 变色放大（现有 matched_keywords 机制平移升级）。

**Rationale**: 不引入新时间轴组件，复用现有字幕列表卡片（用户截图所示页面），改动集中在 SubtitleList.tsx 与 entities；渲染端已支持行内高亮，只需切换数据源。

## R6. 规划期代码审计发现的真实缺陷（顺带修复项）

1. **`codex.py:118` NameError**：`_run_codex_cli` CLI 回退分支引用未定义的 `active_model`（直连失败回退 CLI 时必然崩溃）→ 用 `model_override or config.get_codex_configured_model()` 解析。
2. **`llm_client` 备用端点浪费**：远端供应商 `/responses` 404 后仍重试（见 R2-2）。
3. **composer 小文件回退分支**：`<10KB copyfile` 保留（符合 AGENTS.md 10KB 铁律边界），不动。

## R7. 性能基线（实测）

- 纠偏+高亮（12 句）：直连 17.8s / 每句 ~1.5s；
- 分镜决策（12 句）：codex 代理 112s；直连放宽超时后预估 30~60s（生成 token 更少）；
- ASR（27.8s 视频）：faster-whisper 秒级（现状）；
- 合成：CRF18 fast preset，现状秒级~十几秒（不变）。
- 批量：瓶颈在合成（CPU），决策/纠偏为 IO 等待型；并发调度沿用 constitution IV 硬件感知节流。
