# Tasks: 智能剪辑与自动分镜流水线 (005-auto-edit-pipeline)

**Input**: Design documents from `/specs/005-auto-edit-pipeline/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅ | quickstart.md ✅

**Tests**: 全部 81 用例通过（66 存量 + 15 新增）（spec/plan 明确要求：真实口播固件六断言、决策校验单测、迁移幂等测试、批量契约测试）。测试遵循 AGENTS.md 边界：凡涉 LLM 输出一律固定 embedded 词库引擎或 mock 响应，禁止真实联网调用。

**Organization**: 按用户故事分组，8 个故事（US1~US8）可独立实现与验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1~US8，映射 spec.md）

## Path Conventions

Web 应用：`backend/app/`（FastAPI）+ `frontend/src/`（React SPA）+ `tests/`（pytest，conftest 已隔离临时库）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 基线确认，确保改动前系统处于绿色状态

- [x] T001 在 005-auto-edit-pipeline 分支运行基线测试 `.venv/Scripts/python.exe -m pytest tests/ -q`，确认存量 66 用例全部通过；如有失败先修复再进入后续阶段

**Checkpoint**: 基线绿色，可以开始实现

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共享的模型基座与两个已确认缺陷修复（plan.md Phase A / research.md R6）

**⚠️ CRITICAL**: 任何用户故事开始前必须完成本阶段

- [x] T002 在 backend/app/models/entities.py 新增共享模型：`HighlightWord{word, source: Literal["glossary","ai","manual"]}`、`SceneDecision{part: Literal["hook","body","cta"]="body", broll_category: Optional[MaterialCategory], broll_duration: float=0.0, transition_seconds: float=0.0, material_id: Optional[str]=None, reason: str=""}`；为 `SubtitleSegment` 增加 `highlight_words: List[HighlightWord]=[]` 与 `scene_decision: Optional[SceneDecision]=None`（保留 matched_keywords/matched_category 不删）；为 `EditingStrategy` 增加 `transition_style: str="cut"`（"cut"|"fade"）
- [x] T003 [P] 修复 backend/app/harness_bridge/codex.py `_run_codex_cli` 中 CLI 回退分支引用未定义变量 `active_model` 的 NameError：改为 `active_model = (model_override or config.get_codex_configured_model() or config.LLM_MODEL or "glm-5.3-flash").strip()` 后再 `cmd.extend(["-m", active_model])`（research.md R6-1）
- [x] T004 [P] 修改 backend/app/harness_bridge/llm_client.py `_chat_via_provider`：备用 `/responses` 端点仅当 provider 来源为 codex 本地代理（base_url 含 127.0.0.1 或 source 含 "codex"）时才尝试，远端供应商（如 open.bigmodel.cn）404 直接返回首因错误，杜绝双倍超时浪费（research.md R2/R6-2）
- [x] T005 同步 frontend/src/services/api.ts 的类型定义：SubtitleSegment 增加 `highlight_words?: {word:string; source:'glossary'|'ai'|'manual'}[]`、`scene_decision?: {part:'hook'|'body'|'cta'; broll_category:string|null; broll_duration:number; transition_seconds:number; material_id:string|null; reason:string}`、EditingStrategy 增加 `transition_style:'cut'|'fade'`（依赖 T002 模型定稿）

**Checkpoint**: 模型基座与缺陷修复完成，用户故事可并行开始

---

## Phase 3: User Story 1 — 界面动作收敛：智能剪辑一键直达 (Priority: P1) 🎯

**Goal**: 工具栏只保留一个「智能剪辑」主动作按钮（无「重新」前缀），删除「单步纠错」按钮；后端 `/correct` 端点保留兼容

**Independent Test**: 打开剪辑页检查按钮文案与数量（quickstart V1）

### Implementation for User Story 1

- [x] T006 [US1] 重构 frontend/src/pages/VideoEditor.tsx 顶部工具栏（约 529~572 行区域）：① 删除「单步纠错」按钮块及 `handleCorrectSubtitles` 函数与 `correcting` state（后端 /api/editor/correct 不动）；② 「重新一键智能初剪」按钮（isCachedProject 分支）文案改为「智能剪辑」，title 去掉「重新执行」字样但保留 force=true 重跑行为；③ 未缓存分支按钮文案「⚡ 一键智能初剪与纠偏 (Auto AI Cut)」改为「⚡ 智能剪辑 (AI Auto Cut)」；④ 同步更新 aiFeedback 文案中所有「一键智能初剪与纠偏」为「智能剪辑」

**Checkpoint**: 打开页面 → 仅一个「智能剪辑」按钮、无「单步纠错」；点击可重跑全流程 → US1 独立可验收

---

## Phase 4: User Story 2 — AI 判定高亮词 + 预设高亮词库双引擎 (Priority: P1)

**Goal**: 高亮词三源合并（词库 ∪ AI ∪ 手动）带来源标记，随纠偏流程自动生成并持久化

**Independent Test**: 含「一把过」（词库）与「九月份」（仅 AI 能判）的口播跑智能剪辑，检查每句高亮词合并结果（quickstart V2）

### Tests for User Story 2 ⚠️（先写，确认 FAIL）

- [x] T007 [P] [US2] 新建 tests/test_highlight_words.py：① 固定 embedded 词库引擎跑纠偏，断言含词库关键词（如「一把过」）的句子返回 `highlight_words` 且 source="glossary"；② mock LLM 响应（含 `highlight_keywords:["九月份"]`）走 api_engine `_assemble_response`，断言 AI 词 source="ai" 且与词库词去重合并、matched_keywords 兼容保留

### Implementation for User Story 2

- [x] T008 [US2] 在 backend/app/native_engine/keyword_matcher.py 新增 `build_highlight_words(text: str, ai_keywords: list[str]) -> list[dict]`：词库命中（全部类别关键词）标记 source="glossary"，AI 词标记 source="ai"，按词长度优先去重合并；并在 backend/app/api/editor.py `analyze_and_cut` 组装 SubtitleSegment 时（约 145 行区域）调用它写入 `highlight_words`（依赖 T007 FAIL）
- [x] T009 [P] [US2] 修改两个桥接器的回填逻辑：backend/app/harness_bridge/api_engine.py `_assemble_response` 与 backend/app/harness_bridge/codex.py `correct_subtitles` 中 AI `highlight_keywords` 合并段（api_engine 约 101~104 行、codex 约 378~382 行），除写 matched_keywords 外同步生成 `highlight_words`（AI 词 source="ai"，词库兜底 source="glossary"），保持幂等不重复
- [x] T010 [US2] 运行 `pytest tests/test_highlight_words.py` 全绿，并跑 `pytest tests/test_editor_api.py tests/test_subtitle_strategy.py` 确认无回归（依赖 T008、T009）

**Checkpoint**: 智能剪辑产物中每句字幕带来源标记的高亮词 → US2 独立可验收

---

## Phase 5: User Story 3 — 高亮词在字幕时间轴可视化与可调整 (Priority: P1)

**Goal**: 字幕列表每句下方展示高亮词 chip（来源徽标 + 删除 × + 添加输入），增删即持久化并影响渲染

**Independent Test**: 删一词加一词后渲染成片，新词高亮、被删词恢复普通；重开工程修改仍在（quickstart V3）

### Tests for User Story 3 ⚠️（先写，确认 FAIL）

- [x] T011 [P] [US3] 在 tests/test_subtitle_strategy.py 新增用例：`generate_ass_file` 优先读取 `highlight_words[].word` 做行内高亮，字段缺失时回退 `matched_keywords`（构造两种输入断言 ASS 输出中 `{\c&H...&}` 标记出现/不出现）

### Implementation for User Story 3

- [x] T012 [US3] 修改 backend/app/native_engine/subtitle_styler.py `generate_ass_file`（约 140~156 行区域）：高亮词数据源从 `matched_keywords + custom_words` 切换为 `highlight_words[].word`（无该字段时回退 matched_keywords 保持兼容），策略 `custom_highlight_words` 仍叠加且 source 按 manual 处理（依赖 T11 FAIL）
- [x] T013 [US3] 重构 frontend/src/components/SubtitleList.tsx（约 104~108 行「命中词」纯文本展示处）：改为可交互 chip 列表——每个高亮词一个小标签（glossary=灰/AI=紫/manual=蓝 徽标 + hover × 删除），句尾「+」输入框添加新词（source="manual"）；增删即时调用现有 `PUT /api/projects/{id}/subtitles` 持久化并回调父组件刷新

**Checkpoint**: US1+US2+US3 完成 = **可交付 MVP**（智能剪辑 + 双引擎高亮 + 时间轴调整闭环）

---

## Phase 6: User Story 4 — 四类分镜素材体系与「体验空镜」定名 (Priority: P1)

**Goal**: medical → experience 全链路迁移（DB CHECK 重建 + 磁盘目录 + 词库键 + 前端标签），「体检空镜」更名「体验空镜」

**Independent Test**: 执行迁移脚本（试运行→--apply→重跑幂等），素材库四类标签正确，历史 medical 引用不失效（quickstart V4）

### Implementation for User Story 4

- [x] T014 [US4] 后端枚举与映射同步：backend/app/models/entities.py `MaterialCategory.MEDICAL="medical"` 改为 `EXPERIENCE="experience"`；backend/app/core/config.py `CATEGORIES` 与 `CATEGORY_DIRS`（磁盘目录 storage/materials/medical → experience）；backend/app/native_engine/keyword_matcher.py `keywords.get("medical")` → `get("experience")`；backend/app/api/editor.py `MaterialCategory.MEDICAL` → `EXPERIENCE`（cat_map 约 141~147 行）；backend/app/db/schema.sql materials 表 CHECK 约束改为 `('talking_head','venue','experience','lesson')`（新建库生效）
- [x] T015 [P] [US4] 新建 scripts/migrate_005.py 幂等迁移脚本（对齐 apply_glossary.py 惯例：默认试运行打印 diff、`--apply` 写回、后端运行中拒绝执行）：① SQLite materials 表 CHECK 重建（建新表→CASE WHEN category='medical' THEN 'experience' 拷贝→drop/rename→重建索引，全程事务）；② 磁盘目录 medical→experience 改名（存在才迁）；③ glossary.json `keywords.medical` → `keywords.experience`（原文件备份至 storage/legacy/）
- [x] T016 [P] [US4] 前端标签更新：frontend/src/pages/AssetLibrary.tsx 分类卡（第 8 行）`{ key: 'medical', label: '体检空镜', desc: '体检大厅、视力检测、拍照' }` 改为 `{ key: 'experience', label: '体验空镜', desc: '报名咨询、体检拍照、试学体验、拿证' }`；frontend/src/components/SubtitleList.tsx 徽标映射（约 43~47 行）medical→experience、文案「体检空镜」→「体验空镜」
- [x] T017 [US4] 新建 tests/test_migration_005.py：临时库插入 medical 行执行迁移断言变 experience、旧 glossary 键迁移且备份存在、**重复执行第二遍为 no-op**；并跑 `pytest tests/test_all_flows.py` 验证 experience 分类全链路（上传→匹配→空镜）无回归（依赖 T014、T015）

**Checkpoint**: 素材库四类「口播分镜/场地空镜/体验空镜/教学学车空镜」，历史数据无损 → US4 独立可验收

---

## Phase 7: User Story 5 — AI 分镜决策：切哪里、切多久、怎么转场 (Priority: P1) 核心

**Goal**: 纠偏后新增 AI 决策步骤：逐句输出 part/broll 分类/时长/转场/理由；不切区规则（开场钩子、价格手势句、CTA、情绪叙事）+ 节奏约束（不相邻连续切、占比 ≤40%）提示词与后端确定性校验双保险；合成支持 fade 转场档，音轨恒为口播原声

**Independent Test**: 用萧山报价真实固件跑决策：开场不切、手势句强制不切、CTA 不切、占比 ≤40%（quickstart V5）

### Tests for User Story 5 ⚠️（先写，确认 FAIL）

- [x] T018 [P] [US5] 新建测试固件 tests/fixtures/xiaoshan_price.txt（用户提供校正版 7 句含「不要这个数，也不要这个数，只要这个数」）、tests/fixtures/hangzhou_story.txt（校正版 11 句）、tests/fixtures/female_coach_raw.txt（原始版 20 句），每行格式 `id|start|end|text`
- [x] T019 [P] [US5] 新建 tests/test_scene_decision.py（纯函数单测，不联网）：对 backend/app/native_engine/scene_decision.py 的校验器断言六大行为——① part=hook/cta 句 broll 强制 null；② 文本命中价格手势正则（这个数/这个价/这么多）强制 null（即使 AI 误判 venue）；③ broll_duration>句长裁剪到句长×100%；④ transition 越界 [0,0.5] 裁剪；⑤ 相邻两句均切时裁后句；⑥ 全片占比 >40% 时按单处时长从大到小裁至达标

### Implementation for User Story 5

- [x] T020 [US5] 在 backend/app/harness_bridge/prompting.py 新增 `build_scene_decision_prompt(subs: list[dict]) -> str`：词库背景（load_glossary）+ 三类空镜定义（venue/experience/lesson）+ research.md R8 四类硬性不切区规则 + 节奏约束 + `{id,text,start,end}` 精简输入 + 严格 JSON 输出样例 `{decisions:[{id,part,broll,broll_duration,transition,reason}]}`；**不含高亮词职责**（归纠偏调用）
- [x] T021 [US5] 新建 backend/app/native_engine/scene_decision.py：`parse_decisions(raw: str) -> list[dict]`（复用 llm_client.extract_json）、`validate_and_clip(subtitles, decisions) -> dict[subtitle_id, SceneDecision]`（实现 T019 六大确定性规则）、`fallback_keyword_rules(subtitles) -> dict`（降级路径：复用 keyword_matcher 分类规则 + 默认 60% 句长 + 硬切）
- [x] T022 [US5] 桥接器新增决策通道：backend/app/harness_bridge/api_engine.py 新增 `decide_scenes(subtitles) -> tuple[list, str, float, bool]`（build_scene_decision_prompt + llm_client.chat_completion **timeout=150.0** + parse，失败返回 degraded 标记）；backend/app/harness_bridge/codex.py 同签名实现（`_run_codex_cli(prompt, timeout=150.0)`）；两者均走 T021 校验器，embedded 引擎无此能力直接走降级（依赖 T020、T021）
- [x] T023 [US5] 接入主流程：backend/app/models/entities.py `PipelineStage` 增加 `SCENE_DECIDING = "scene_deciding"`（85% 档）；backend/app/api/editor.py `analyze_and_cut` 在纠偏后、关键词匹配前插入第 3.5 步（`AnalyzeAndCutRequest` 新增 `enable_scene_decision: bool = True`）：调 decide_scenes → 成功则写入各句 `scene_decision` 并按分类随机落定 material_id，失败/降级则用 fallback_keyword_rules 并在项目 `pipeline_notes` 如实标注（progress 消息含「已降级」）；`/progress` 端点发布 SCENE_DECIDING 阶段
- [x] T024 [US5] backend/app/api/editor.py 新增 `POST /{project_id}/scene-decision` 端点（契约 C3）：对既有工程不重转写单独重跑决策，返回 `{code:0, data:{subtitles(仅 id+scene_decision), engine_used, latency_ms, degraded}}`
- [x] T025 [US5] backend/app/native_engine/ffmpeg_filter.py `compose_jl_cut` 新增 fade 转场档：`strategy.transition_style=="fade"` 且相邻片段转场 >0 时用 `xfade=transition=fade:duration=D:offset=累计时长` 链式替代 concat（offset 逐段累计、浮点容错）；**音频始终 `-map 0:a` 不参与滤镜**；cut 档走现状 concat 不动（依赖 T002 transition_style）
- [x] T026 [US5] 前端呈现：frontend/src/components/SubtitleList.tsx 每句显示 part 分段徽标（hook=橙/body=灰/cta=绿）+ scene_decision 空镜标签（分类/时长/理由 tooltip）；frontend/src/components/StrategyStudio.tsx 新增「转场风格」单选（硬切 cut / 叠化 fade 0.3~0.5s），走现有 PUT strategy 保存
- [x] T027 [US5] 集成验证：`pytest tests/test_scene_decision.py tests/test_editor_api.py` 全绿；用萧山固件手动跑一次真实决策（直连 API），人工核对不切区与节奏（预期结果见 research.md R8）

**Checkpoint**: 时间轴带叙事分段与空镜标签，成片转场可选叠化且语音连续 → US5 独立可验收

---

## Phase 8: User Story 6 — 批量剪辑与单视频人工修正工作台 (Priority: P2)

**Goal**: 多选口播视频批量走全流水线，队列按硬件并发执行，失败项落真实错误，可点入单视频工作台修正

**Independent Test**: 3 个视频批量剪辑（含 1 个损坏文件）观察队列与错误透传（quickstart V6）

### Implementation for User Story 6

- [x] T028 [US6] 批量任务持久化：backend/app/db/schema.sql 新增 `batch_jobs(id TEXT PK, payload_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','finished')), created_at REAL)`；backend/app/db/repository.py 新增 BatchJobRepository（save/get_by_id/list_recent）
- [x] T029 [P] [US6] 新建 backend/app/api/batch.py：`POST /api/batch/submit`（material_ids 校验存在性、并发数取 HardwareMetrics.recommended_concurrency、后台线程池逐个执行完整流水线：analyze→决策→render，单项失败落真实 error 不中断其余）+ `GET /api/batch/{job_id}`（返回 items 进度/状态/error，契约 C4）；backend/app/main.py 注册 router
- [x] T030 [P] [US6] 新建 tests/test_batch_api.py：monkeypatch 掉 ASR/composer（测试隔离边界内 mock），断言 submit 返回 job_id 与 queued 数、轮询到 completed、损坏素材项 status=failed 且 error 非空、其余项继续完成
- [x] T031 [US6] 批量前端：frontend/src/services/api.ts 新增 submitBatch/fetchBatch 封装；frontend/src/pages/AssetLibrary.tsx 口播分镜卡片多选（checkbox）+「批量智能剪辑」按钮 + 队列进度面板（逐项进度/状态/错误，复用现有 progress 样式）+ 完成项「进入工作台」链接跳转 VideoEditor（复用现有路由参数 initialSelectedTalkingHeadId）

**Checkpoint**: 批量队列可见、失败如实、单视频可点入修正 → US6 独立可验收

---

## Phase 9: User Story 7 — 标题横幅与水印默认关闭 (Priority: P2)

**Goal**: 新建工程默认 `enable_top_banner=false`、`enable_watermark=false`；策略工坊保留完整开关；存量工程不受影响

**Independent Test**: 新工程渲染无横幅水印，手动开启后渲染出现（quickstart V7 前半）

### Implementation for User Story 7

- [x] T032 [US7] backend/app/models/entities.py `EditingStrategy` 默认值：`enable_top_banner: bool = True` → `False`、`enable_watermark: bool = True` → `False`（仅影响新建工程的默认构造，迁移不回写已保存策略——T017 迁移测试中加断言：存量策略 JSON 里的 True 不被改写）
- [x] T033 [P] [US7] frontend/src/components/StrategyStudio.tsx 横幅与水印两个设置区块（约 436、649 行）：区块头部默认折叠态呈现「已关闭（成片评审后可开启）」提示文案，展开后开关与样式能力保持不变

**Checkpoint**: 新工程成片无横幅水印 → US7 独立可验收

---

## Phase 10: User Story 8 — 视频封面字段与接口预留 (Priority: P3)

**Goal**: 工程支持设置封面（成片截帧/本地上传），AI 生成入口显式 501「规划中」

**Independent Test**: 选帧设封面 → 重开工程封面仍在；AI 入口点击提示规划中（quickstart V7 后半）

### Implementation for User Story 8

- [x] T034 [P] [US8] backend/app/models/entities.py `CutProject` 新增 `cover_image_path: Optional[str]=None`、`cover_source: Optional[Literal["frame","upload","ai"]]=None`；backend/app/core/config.py 新增 `COVERS_DIR = STORAGE_DIR / "covers"` 并加入启动建目录列表
- [x] T035 [US8] backend/app/api/editor.py 新增 `POST /{project_id}/cover`（契约 C5）：`source="frame"` 时用 `ffmpeg -ss {timestamp} -frames:v 1` 从当前成片截帧存 covers/ 并持久化字段；`source="upload"` 接收图片文件（复用 ensure_storage_path 路径守卫）；`source="ai"` 返回 `501 {"code":40901,"message":"AI 封面生成规划中，敬请期待"}`（真实执行铁律：不返回伪成功）
- [x] T036 [US8] 前端封面入口：frontend/src/pages/VideoEditor.tsx 成片预览区（output_video_url 播放器旁）新增「设为封面」按钮（取当前播放时间戳截帧）+ 已设封面缩略图展示；frontend/src/services/api.ts 封装 setProjectCover

**Checkpoint**: 封面持久化闭环，AI 入口诚实占位 → US8 独立可验收

---

## Phase 11: Polish & Cross-Cutting Concerns

- [x] T037 运行全量回归 `.venv/Scripts/python.exe -m pytest tests/ -q`，全部用例（存量 66 + 新增）通过
- [ ] T038 [P] 按 specs/005-auto-edit-pipeline/quickstart.md 完成 V1~V7 全部人工验收场景并记录结果（**待用户在 GUI 中执行**；自动化可达部分已验证：V5 分镜决策真实调用六断言通过、V4 迁移单测通过、批量/封面契约测试通过）
- [x] T039 提交全部实现（Mimosa 提交前扫描通过），更新 specs/005-auto-edit-pipeline/tasks.md 勾选状态，确认 AGENTS.md SPECKIT 指向 005 plan.md 无需变更

---

## Phase 12: User Story 9 — ASR 物理词时间戳与语义自然断句 (Priority: P1) 🎯

**Goal**: 彻底消除 10 字机械等分导致的腰斩错位，基于物理声学词时间戳与中文语义停顿切分子句，词语完整、时间精准

**Independent Test**: 输入长句口播，断言切分后词组（“没有”、“我们”、“安吉这边”）完整不跨句切断，每句 6~12 字，时间戳精准吻合发音

- [x] T040 [P] [US9] 在 tests/test_subtitle_merge.py 新增自然语义断句与词时间戳测试用例：断言长口播输入切分后词组不被切碎且起止时间严格对应发音，无线性平摊
- [x] T041 [US9] 重构 backend/app/native_engine/asr_runner.py 中的 `transcribe` 与 `split_into_readable_segments`：彻底移除 `chunk_len = 10` 等分切片，利用 Whisper 词物理时间戳（word_timestamps=True）及自然意群停顿进行 6~12 字黄金切分
- [x] T042 [US9] 运行 `pytest tests/test_subtitle_merge.py` 验证断句重构单测全部通过

---

## Phase 13: User Story 10 — 开场分镜节奏优化与前序空镜补齐 (Priority: P1)

**Goal**: 开场 1.5s~2s 保持口播真人出镜（建立主播人设与信任），2s 后出现地理场地词（如“湖州驾校 / 安吉校区”）可自然切入 2.0s~3.5s 场地空镜

**Independent Test**: 真实口播测试，断言 2s 后命中场地词的句子获得空镜决策，报价手势句依然 100% 保持真人出镜

- [x] T043 [P] [US10] 在 tests/test_scene_decision.py 新增开场分镜节奏测试：验证 2s 后的地域词（安吉/湖州）成功生成场地空镜，且报价手势句依然不切
- [x] T044 [US10] 修改 backend/app/harness_bridge/prompting.py `build_scene_decision_prompt`：更新开场规则为“开场前 1.5~2 秒真人出镜亮相（建立主播信任感与人设），2 秒后若提到地域/校区/场地或流程，可自然切入相应空镜（如 venue/experience）”
- [x] T045 [US10] 修改 backend/app/native_engine/scene_decision.py `_infer_part` 与 `validate_and_clip`：不再根据 `index == 0` 恒判 hook 全裁，改基于时间戳（start_time < 1.8s 为 hook 保护），允许 2s 后命中 venue/experience 的句子生成 2.0s~3.5s 分镜决策
- [x] T046 [US10] 运行 `pytest tests/test_scene_decision.py` 验证开场分镜规则放宽与手势保护单测全绿

---

## Phase 14: User Story 11 — 独立工程目录规划 (Priority: P1)

**Goal**: 建立 `storage/tasks/YYYYMMDD_HHMMSS_{视频名}/` 架构，将原始视频、音频、字幕、压制成片与封面统一独立归档

**Independent Test**: 剪辑一个视频，检查磁盘在 storage/tasks/ 下是否创建了格式为 YYYYMMDD_HHMMSS 的独立文件夹并完整存放所有产物

- [x] T047 [P] [US11] 在 backend/app/core/config.py 新增 `TASKS_DIR = STORAGE_DIR / "tasks"`，启动时自动创建；新增 `create_task_dir(title: str) -> Path` 按 `YYYYMMDD_HHMMSS_{safe_stem}` 生成独立工程工作区
- [x] T048 [US11] 更新 backend/app/models/entities.py 与 backend/app/db/repository.py：在 `CutProject` 模型中新增 `task_dir: Optional[str] = None` 字段并持久化到 SQLite
- [x] T049 [US11] 重构 backend/app/api/editor.py 工程创建与渲染归档逻辑：新工程中间音频、.srt/.ass 字幕、压制成片统一保存在专属 `task_dir` 目录下，并提供返回工程目录与打开所在文件夹的能力

---

## Phase 15: User Story 12 — 批量混剪生产中心重构 (Priority: P1)

**Goal**: 批量混剪页面作为核心生产中心，支持口播多视频直接上传，实时多阶段进度看板，成片以卡片网格整齐排列（显示封面、时长、时间、打开文件夹、播放），点击卡片直接下钻到剪辑工作台

**Independent Test**: 在批量混剪页面多选视频上传，看到各任务实时进度，完成后呈现卡片网格，点击卡片直接跳入工作台精修

- [x] T050 [P] [US12] 在 backend/app/api/batch.py 新增 `POST /api/v1/batch/upload-and-cut` 端点：支持多口播视频一次性上传，自动为每个视频创建 `YYYYMMDD_HHMMSS` 独立工程目录并投递批量剪辑作业
- [x] T051 [US12] 重构 frontend/src/pages/BatchCut.tsx：增加批量口播视频拖拽/多选上传区；增加实时多阶段进度条看板；彻底用成片卡片网格 (Card Grid) 取代旧日志列表，每张卡片展示成片缩略图、文件名、时长、生成时间、播放按钮与打开文件夹按钮；卡片配备「单点进入工作台」按钮，支持跳转携带 project_id

---

## Phase 16: User Story 13 — 剪辑工作台单传入口与 Title/水印圆点交互重塑 (Priority: P1)

**Goal**: 工作台支持直接拖入/上传单视频开剪；彻底移除“成片评审后可开启”阻断文案，重构 Title 横幅与品牌水印为直观圆点开关（点击开启实心、再点空心取消）

**Independent Test**: 在策略工坊点击开启 Title 与水印，确认圆点高亮实心，再次点击变为空心取消；工作台工具栏点击单传视频即可开剪

- [x] T052 [P] [US13] 修改 frontend/src/components/StrategyStudio.tsx：彻底移除“已关闭（成片评审后可开启）”阻断说明文案；重构 Title 挂顶横幅与品牌水印为直观的圆点 Toggle / Checkbox（点击开启高亮实心圆点、再次点击恢复空心圆点取消），即点即改
- [x] T053 [US13] 重构 frontend/src/pages/VideoEditor.tsx：彻底移除顶部原生 `<select>` 下拉框，替换为工程视频卡片展开抽屉/横栏；顶部工具栏增加「+ 上传口播视频」就地开剪按钮；接收从批量混剪页面携带的 initialProjectId 或 URL 参数，实现秒级载入目标工程

---

## Phase 17: User Story 14 — 素材管理库纯化 (Priority: P2)

**Goal**: 从素材库彻底剥离 `talking_head` 口播分镜标签页，纯化为三大纯空镜库（场地、体验、教学），引导待剪口播前往批量混剪或工作台

**Independent Test**: 打开素材库页面，确认仅有场地空镜、体验空镜、教学学车空镜 3 个标签，顶部有口播上传指引提示

- [x] T054 [US14] 修改 frontend/src/pages/AssetLibrary.tsx：移除 `talking_head` 标签页，仅保留【场地空镜】、【体验空镜】、【教学学车空镜】三大分类；并在页面顶部添加指引提示：“口播主视频请前往「批量混剪」或「剪辑工作台」上传”

---

## Phase 18: Polish & E2E Validation

- [x] T055 前端代码执行 `pnpm build` 确认零 TypeScript 报错、零样式引用警告
- [x] T056 运行全量回归测试确认全部测试绿色通过

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 Setup
  └→ Phase 2 Foundational
       ├→ Phase 3 US1 (界面收敛)
       ├→ Phase 4 US2 (双引擎高亮) → Phase 5 US3 (时间轴调整)
       ├→ Phase 6 US4 (体验空镜) → Phase 7 US5 (AI分镜决策) → Phase 8 US6 (批量基础)
       ├→ Phase 9 US7 (默认关闭)
       ├→ Phase 10 US8 (封面预留)
       ├→ Phase 12 US9 (物理词时间戳与语义断句) ── 核心质量攻坚
       ├→ Phase 13 US10 (开场分镜节奏优化)
       ├→ Phase 14 US11 (YYYYMMDD_HHMMSS 独立目录)
       ├→ Phase 15 US12 (批量生产中心 & 卡片网格)
       ├→ Phase 16 US13 (工作台单传 & 水印圆点开关)
       └→ Phase 17 US14 (素材库纯化)
            └→ Phase 18 Polish (编译与测试收尾)
```

### User Story Dependencies

- **US1**：仅前端单文件，Foundational 后立即可做，与其他故事零耦合
- **US2 → US3**：US3 的 chip UI 与渲染消费 US2 产出的 highlight_words 数据
- **US4 → US5**：决策输出的 broll 枚举含 experience，迁移先行避免枚举分裂
- **US5 → US6**：批量执行的是「含决策」的完整流水线
- **US7 / US8**：互相独立，可穿插在任意间隙

### Within Each User Story

测试先行（标注 ⚠️ 的任务先写并确认 FAIL）→ 模型/服务 → 端点 → 前端 → 集成验证

### Parallel Opportunities

- Foundational 内：T002 / T003 / T004 三文件互斥可并行（T005 等 T002）
- US2 内：T007（测试）与 T009（桥接器）可并行起草
- US4 内：T015（脚本）/ T016（前端）与 T014 并行
- US5 内：T018 / T019 固件与单测可并行先行
- US6 内：T029（端点）与 T030（契约测试）可并行
- 跨故事：US7、US8 全程可与任何故事并行

---

## Parallel Example: US5 冲刺段

```bash
# 固件 + 单测并行（无实现依赖）：
Task: "T018 测试固件三份口播文本入 tests/fixtures/"
Task: "T019 决策校验器六断言单测 tests/test_scene_decision.py"
# 随后串行核心链：
Task: "T020 提示词工厂" → "T021 校验/降级模块" → "T022 桥接通道" → "T023~T025 主流程/端点/合成" → "T026 前端"
```

---

## Implementation Strategy

### MVP First（推荐首个可交付增量：US1 + US2 + US3）

1. Phase 1 + Phase 2 完成 → 基线绿、缺陷清零
2. US1 界面收敛（半天级）→ US2 双引擎高亮 → US3 时间轴闭环
3. **STOP & VALIDATE**：quickstart V1~V3 逐项过 → 这已是一个对外可演示的完整增量

### Incremental Delivery

- 增量二：US4 迁移 + US5 AI 分镜决策（本特性的核心价值，验收看萧山固件六断言）
- 增量三：US6 批量（生产力规模化）
- 随时可插入：US7（默认值，一行级）、US8（封面，接口预留）

### Notes

- [P] 任务 = 不同文件、无未完成依赖；同一文件的任务一律串行（如 entities.py 出现在 T002/T014/T023/T032/T034，天然被阶段顺序串开）
- 每完成一个任务或逻辑组即 commit；Mimosa 提交前扫描为强制门
- 真实执行铁律：所有 AI/合成失败路径如实报错或显式降级标注，严禁伪成功；凭据零明文出后端
