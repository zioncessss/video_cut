<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/010-portrait-filter-enhancement/plan.md
<!-- SPECKIT END -->

## 🚨 严禁测试函数替代真实运行准则 (Real Execution & Anti-Mock Rules)
1. **禁止假运行与模拟数据替代 (No Mock/Fallback for Real Workflows)**：
   - 在真实工程链路（ASR 语音转写、大模型纠错与指令理解、FFmpeg 视频压制与播放）中，必须严格调用真实的底层引擎。
   - **对于用户上传或系统已有真实素材（文件大小 > 10KB），严禁在发生错误或超时时静默回退到预置示范文字（如“自建五万平训练场”）或直接复制原文件假装合成成功！**
   - 真实链路失败时必须立即抛出真实异常或返回明确错误详情，如实反馈给用户并驱动定位，绝不允许以“成功”掩盖根本问题。
2. **模型真实性准则 (Truthful Model Identity)**：
   - 严禁在界面或配置中硬编码假模型名（如 `gpt-4o-mini`）。
   - 当前使用的模型必须 100% 动态读取自用户本地真实配置（`~/.codex/config.toml`），并在调用与界面展示中如实呈现（如 `glm-5.3-flash`）。
3. **测试代码隔离准则 (Test Isolation)**：
   - 测试专用的 Mock、假数据或快速桩函数仅允许存在于 `tests/` 目录中。
   - 生产代码（`backend/app/`）中不得为了让单测通过而向真实业务注入静默伪造数据的逻辑。

## 📌 全链路架构事实与数据边界 (Architecture Facts & Data Boundaries)
1. **词库唯一事实源 (Glossary Single Source)**：
   - `storage/glossary.json` 是 ASR 热词（initial_prompt）、同音错字纠偏映射、受保护词、关键词高亮的**唯一配置源**，按 mtime 缓存、编辑即生效。
   - 严禁在任何桥接器、提示词或脚本中硬编码纠偏词表：LLM 纠错提示词一律经 `backend/app/harness_bridge/prompting.py` 生成，确定性替换一律走 `config.apply_glossary_corrections()`（长词优先、幂等）。
   - 词库文件缺失/损坏时纠偏链路必须空转并显式告警，严禁回填任何预置业务文案。
2. **ASR 原文不可篡改**：
   - `raw_text` 与 `raw_asr_segments` 是真实识别结果，任何纠偏只允许写入 `corrected_text`；历史纠偏流水 `corrections_summary` 保持原样。
   - 存量数据纠偏统一使用 `scripts/apply_glossary.py`（默认试运行，`--apply` 写回，自动备份，后端运行中会拒绝执行）——**严禁手写一次性脚本直改存储文件**。
3. **SQLite 是权威存储**：
   - 权威库为 `storage/videocut.db`（环境变量 `VIDEOCUT_DB_PATH` 可覆盖；数据根目录 `VIDEOCUT_STORAGE_DIR`）。
   - `storage/projects/*.json` 与 `materials_meta.json` 只是迁移期影子文件：应用加载时 SQLite 优先，**手改 JSON 会被无视或被内存缓存覆盖，不构成修复手段**。存储层正在收敛为 SQLite 单一权威（迁移后 JSON 归档至 `storage/legacy/`，详见 specs/004 plan.md 决策修订记录）。
4. **Harness 统一契约与分层调用**：
   - 所有桥接器（embedded/codex/zcode/api/未来新增）的 `correct_subtitles` 必须返回 `HarnessCorrectionResponse`；纠偏知识必须经 `prompting.build_correction_prompt()` 注入并对返回结果做词库确定性兜底，禁止自带私有钱表或自定返回结构。
   - **Tier A（固定格式任务，如字幕纠偏）默认走 `api` 直连引擎**（OpenAI 兼容 `/chat/completions`，共享传输层 `harness_bridge/llm_client.py`；仅 `api` 引擎使用设置页的 base_url/api_key/model/协议，配置优先级：设置页 → `~/.codex/config.toml` → 显式报错，模型名如实展示）。API Key 仅允许在本机 settings.json 存储并仅用于直连请求的 Authorization 头；**严禁在任何日志、API 响应、测试或文档中读取、展示或转发明文 key**。
   - **引擎切换时配置必须随之隔离**：`codex` 引擎的提供方强制绑定 `llm_client.codex_provider()`（只读 `~/.codex/config.toml` 本地代理/CLI，绝不读设置页 API 配置）；`zcode` 引擎直接启动本地 CLI 进程、使用其自身登录态；设置页 UI 按当前引擎切换显示对应配置区。**凭据红线**：token/api_key 值严禁下发到前端或写入任何对外输出——`GET /settings` 的 `engine_config` 只允许返回 `has_token`/`has_key` 布尔态，任何 Agent 与代码都不得读取、缓存或上传凭据明文。
   - **Tier B（开放式任务，如自由剪辑指令、聊天）与 active_harness 解耦**，固定路由 `factory.get_tier_b_harness()`（codex > zcode > embedded）；上下文纪律：只传摘要（字幕 id+文本+时长、分类计数），严禁 dump 全量工程/素材模型字段；提示词在 `prompting.py` 中按任务严格分函数，互不掺杂。
   - **embedded 引擎仅具备词库确定性纠偏能力**（Tier A 离线兜底），不具备开放式指令理解/聊天能力——这些调用必须显式报错，严禁返回预置话术或假装成功；不存在的功能（如批量混剪规划）不得实现 Stub。
5. **测试数据边界**：
   - `tests/conftest.py` 已将数据库重定向到临时库，测试不得读写真实 `storage/videocut.db`。
   - 凡断言 LLM/纠错输出的测试，必须固定 embedded 词库引擎或 mock CLI 响应，禁止依赖真实 codex/zcode 联网调用（输出随模型波动，必然产生偶发失败）。

## 🛡️ 高亮词与视觉策略全生命周期不丢失准则 (Highlight & Visual Strategy Integrity Rules)
1. **高亮词全生命周期无损传递 (Zero Loss Across Entire Lifecycle)**：
   - 任何涉及字幕、策略流转的环节（ASR 转写、大模型决策、磁盘自愈、工程保存、字幕编辑、重新合成、倍速渲染），必须保证 `highlight_words` 与关键词元数据 100% 无损传递。
   - 严禁任何自愈、迁移或更新函数以“空列表 `[]`”冲掉存量高亮词。客户端传入空列表时，服务端必须做防御性合并（优先保留存量词，无词时自动调用 `build_highlight_words` 规则自愈）。
2. **渲染压制层零信任防御兜底 (Zero-Trust Defensive Rendering)**：
   - 当策略开启高亮（`enable_highlight = True`）时，`generate_ass_file` 必须具备防御底线：若字幕因任何原因丢失高亮词，渲染层必须就地触发 `build_highlight_words(text)` 自愈提取，**绝对不允许静默压制成无高亮的纯白白板成片**。
3. **集成测试真实性准则 (End-to-End Test Integrity)**：
   - 严禁测试仅通过手工注入 `highlight_words` 的 mock 数据测试单个渲染函数而忽视上游输入状态。
   - 关键工程链路（磁盘自愈 -> 工程载入 -> 字幕更新 -> ASS生成与压制）必须具备真实的端到端集成测试（如 `test_highlight_pipeline_integrity.py`），严格断言产物中包含高亮标签，防止“单测 100% 绿灯、真实业务却已损坏”的伪安全感。

