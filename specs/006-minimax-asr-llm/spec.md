# Feature Specification: MiniMax 统一接管 ASR 语音识别与大模型智能剪辑 (006-minimax-asr-llm)

**Feature Branch**: `006-minimax-asr-llm`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "需要把asr和文本转接 minimax，所以要先测试一下怎么写请求，函数怎么变化，文档在https://platform.minimax.cn/docs/api-reference/api-overview，然后我给你提供api key"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - MiniMax 极速语音识别 (Speech-to-Text) 与字级时间戳对齐 (Priority: P1)

用户导入待剪辑口播视频后，系统提取 16kHz 纯净音频并通过 MiniMax 极速 ASR 云端接口在数秒内完成转写。接口返回包含每个字符/词汇的毫秒级声学起止时间（`start`, `end`），直接输送给既有的 6~12 字黄金视读意群切分管线，彻底解放本地 CPU 占用并解决发热卡顿。

**Why this priority**: 本地 CPU Whisper 推理耗时过长（60秒视频耗时30~70秒）且中文专有词容易音近漏错，MiniMax ASR 是大幅提升全流程剪辑速度与体验的基础。

**Independent Test**: 上传一段 60 秒测试视频，触发 ASR 识别，断言 5 秒内返回完整文本与各字时间戳，且本地 CPU 不出现过载。

**Acceptance Scenarios**:

1. **Given** 系统已配置有效 MiniMax 凭据，**When** 用户上传或批量混剪口播视频，**Then** 系统调用 MiniMax STT 接口并在 2~5 秒内返回完整字幕文本与逐字物理时间戳。
2. **Given** 接口返回单字时间戳列表，**When** 进入智能切分流程，**Then** 顺利聚合为 6~12 字健康短句并正确保留发音起止时间。
3. **Given** 用户未配置云端 Key 或处于离线断网环境，**When** 触发 ASR 识别，**Then** 系统自动降级使用本地 faster-whisper 执行转写，不阻断剪辑工作流。

---

### User Story 2 - MiniMax 大模型统一接管智能字幕纠偏与分镜决策 (Priority: P1)

系统将大语言模型统一切换至 MiniMax 旗舰语言模型（`MiniMax-Text-01`），承担 Tier A 字幕纠偏与 Tier B 视觉分镜决策任务。通过标准 OpenAI 兼容协议直连，严格结合 `storage/glossary.json` 词库纠正错字、规整标点，并依据短视频开场 Hook 保护、报价手势不切区、空镜占比与转场风格输出结构化 JSON 决策。

**Why this priority**: MiniMax 语言模型具备出色的中文语义理解与高稳定性结构化输出，且单次决策成本不足 1 分钱，与 ASR 形成统一闭环。

**Independent Test**: 提供含有错别字与特定驾校术语的字幕列表，调用纠偏与分镜接口，断言 MiniMax-Text-01 正确输出符合 JSON Schema 的纠错与分镜切分结果。

**Acceptance Scenarios**:

1. **Given** 口播字幕存在专有名词错别字，**When** 触发 Tier A 智能纠偏，**Then** MiniMax 模型输出严格符合契约的 JSON，准确修正错字并给出修改原因。
2. **Given** 纠偏后的字幕列表，**When** 触发 Tier B 分镜决策，**Then** MiniMax 模型逐句识别 part（hook/body/cta）、匹配空镜分类、建议切入时长与转场，严守不切区规则。

---

### User Story 3 - 设置中心 MiniMax 统一凭据配置与连通性检测 (Priority: P2)

在系统「设置」页面中，用户可集中配置 MiniMax API Key、选择模型名称（`MiniMax-Text-01`）与启用云端极速 ASR 开关，支持一键点击「测试连通性」同时检测 LLM 与 ASR 双通道健康状态。系统遵循严格的凭据保护红线，界面与对外接口仅返回布尔态，严禁明文泄露。

**Why this priority**: 面向桌面端非技术用户，提供开箱即用、一处配置全线生效的交互体验。

**Independent Test**: 在设置页输入 MiniMax Key 点击保存并测试，断言显示连通成功，刷新页面确认状态正常持久化且密钥不以明文外露。

**Acceptance Scenarios**:

1. **Given** 用户在设置页输入 MiniMax 凭据，**When** 点击保存，**Then** 配置写入本地 `storage/settings.json` 并即时生效。
2. **Given** 配置完成，**When** 点击测试连通性，**Then** 系统分别向 MiniMax Chat 与 STT 发送轻量探针，前端反馈双通道就绪状态。

---

### Edge Cases

- **超长音频（>500秒）**：MiniMax 单次 STT 限制为 500 秒，针对极少见的大长视频，系统应在提取音频后按 300 秒为界自动分片转写后合并时间戳；
- **网络波动或 MiniMax 接口超时**：云端 ASR 请求设置 60 秒超时，超时或返回错误时记录真实日志并自动切换至本地 faster-whisper 兜底；
- **账户欠费或 Key 失效**：接口如实拦截并友好反馈给用户“MiniMax 接口鉴权失败或余额不足”，严禁使用假数据伪装成功。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供基于 MiniMax `asr-1.0` 模型的云端极速语音识别适配器；
- **FR-002**: ASR 请求必须使用 `multipart/form-data` 上传 16kHz WAV 音频，指定 `response_format="verbose_json"` 与 `timestamp_level="word"`；
- **FR-003**: 系统必须将 MiniMax 返回的逐字 `segments` 转换为统一的 `words: [{word, start, end}]` 数据结构，无缝对接既有断句与字幕样式引擎；
- **FR-004**: 系统必须支持在设置中一处配置 MiniMax Key，同时供给 ASR 与 LLM（纠偏、分镜、对话）使用；
- **FR-005**: 系统必须保留本地 Faster-Whisper 作为无网或云端故障时的自动离线降级方案；
- **FR-006**: 严格执行安全红线，API Key 仅在 `storage/settings.json` 本地持久化，禁止在任何外部日志、前端 API 响应中暴露明文；
- **FR-007**: 设置中心必须提供 ASR 服务状态展示与一键联通性检测能力。

### Key Entities

- **ASRProvider**: 标识当前转写底层，枚举包括 `minimax`（云端极速）与 `local`（本地 Faster-Whisper）；
- **MiniMaxWordSegment**: MiniMax 接口响应的字级声学单元，包含 `id`, `start`, `end`, `text`, `speaker`；
- **EngineSettings**: 扩展后的系统引擎配置模型，包含统一的 `llm_api_key`, `llm_base_url`, `llm_model`, `asr_provider`。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 60 秒标准口播视频的语音识别耗时由本地 CPU 的 30~70 秒缩减至 2~5 秒，转写效率提升 **85% 以上**；
- **SC-002**: 单条短视频的 ASR 与大模型剪辑双项合计 API 成本稳定在 **0.06 元人民币以内**；
- **SC-003**: 字符物理时间戳精确度达到毫秒级，短视频字幕无跳字、无声画错位；
- **SC-004**: 云端服务异常或网络离线时，系统能在 3 秒内平滑切换至本地引擎，流水线成功率达 100%。

## Assumptions

- 用户机器具备网络访问能力，可顺畅连接 MiniMax 官方 API 域名 `https://api.minimaxi.com`；
- 用户的 MiniMax 账户已完成实名认证且具备调用余额；
- 短视频口播时长绝大多数在 15 秒至 180 秒之间（符合 500 秒单次转写上限）；
- 本地依然保留预置的 ffmpeg 与 faster-whisper 依赖，确保断网环境下的功能完整性。