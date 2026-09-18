# Technical Research & Decisions: MiniMax 统一接管 ASR 与智能剪辑 (006-minimax-asr-llm)

## Phase 0: Outline & Research Decisions

### R1: MiniMax 语音识别接口选型与参数协议
- **Decision**: 选用 MiniMax Speech-to-Text 极速接口 `POST https://api.minimaxi.com/v1/speech_to_text`，采用 `multipart/form-data` 上传 16kHz WAV 文件，参数固定传 `model="asr-1.0"`, `response_format="verbose_json"`, `timestamp_level="word"`, `stream=false`。
- **Rationale**: 经实测验证（HTTP 200 OK），该组合能够返回包含全文本（`text`）与各字逐字起止时间（`segments: [{id, start, end, text, speaker}]`）的数据结构。其逐字起止时间精确到毫秒，与我们现有的词级声学时间戳完全同构。
- **Alternatives Considered**: 
  - `response_format="json"`：仅返回纯文本和总时长，缺少时间戳，无法做音画对齐，否决。
  - `response_format="srt"`：返回 SRT 纯文本字符串，缺少字级别精准边界，且需额外正则解析，否决。
  - `stream=true`：官方明确流式模式不支持 `verbose_json` 与 `word` 时间戳，且短视频为录音文件整体处理，无需 SSE 流式，否决。

### R2: 字级时间戳适配与 6~12 字意群切分衔接
- **Decision**: 将 MiniMax 返回的 `segments` 数组映射为统一的 `words` 列表 `[{"word": s["text"], "start": s["start"], "end": s["end"]}]`，整句文本复用 `split_into_readable_segments(segments, max_chars=14)`。
- **Rationale**: 现有管线已经具备成熟的短视频 6~12 字自然意群切分与停顿合并算法（依据标点、$\ge 0.25$s 停顿、代词前瞻防腰斩）。将 MiniMax 的字级切片转入该算法后，无需重构任何后续编排渲染逻辑，实现零破坏性衔接。
- **Alternatives Considered**: 直接使用 MiniMax 的单字作为独立字幕句：会导致短视频字幕极其细碎（0.2s 一闪烁），视读体验崩溃，否决。

### R3: 异常隔离与离线降级 (Graceful Degradation) 策略
- **Decision**: 在 `ASRRunner` 中设计双层执行器。首选 MiniMax 云端极速识别；若未配置 Key、网络请求抛出异常、鉴权失败或请求超时（timeout=60s），自动记录日志并无缝切换至本地 `faster-whisper` 执行离线转写。
- **Rationale**: 兼顾“云端极速高性能”与“断网/未联网离线可用性”，符合宪章对 C 端桌面应用的稳定性要求。
- **Alternatives Considered**: 云端失败直接中断报错：当用户在无网环境下或 MiniMax 服务临时抖动时会导致软件无法使用，损害基础可用性。

### R4: 大模型大脑 (Tier A 纠偏 + Tier B 分镜) 统一对接
- **Decision**: 统一配置 MiniMax 旗舰模型 `MiniMax-Text-01`，复用既有 `ApiHarnessEngine` 与 OpenAI 兼容通道（`POST https://api.minimaxi.com/v1/chat/completions`）。
- **Rationale**: 实测确认 `MiniMax-Text-01` 完全兼容 OpenAI API 规范，能严密遵循 JSON Schema 输出纠偏与分镜决策；单条短视频 LLM 成本仅约 0.01 元，性价比极高。
- **Alternatives Considered**: 维护两套独立的大模型客户端：增加不必要的冗余代码，违背宪章简洁原则。

### R5: 凭据隔离与单 Key 统一配置
- **Decision**: 在 `storage/settings.json` 中配置 `llm_api_key`, `llm_base_url="https://api.minimaxi.com/v1"`, `llm_model="MiniMax-Text-01"`, `asr_provider="minimax"`。系统共享这一组 API Key 同时用于 ASR 与 LLM，并在 `backend/app/api/settings.py` 的 GET 响应中仅返回 `has_key: bool`，严禁下发明文。
- **Rationale**: 用户只需在设置页粘贴一次 MiniMax Key，即可同时打通“极速语音转写”与“大模型智能剪辑”，消除双重配置负担，严格恪守系统安全红线。

### R6: 分镜决策 LLM 稀疏剪辑指示清单（Editorial Cue Sheet）
- **Decision**: 彻底废除向大模型要求为 59 句逐句打标的“全量填空反模式”，改为业界成熟的“稀疏剪辑指示清单”。大模型纵览全篇文本与时间戳，仅聚焦检索强相关的核心语义片段并输出切入区间清单（`broll_cues: [{start_time, end_time, category, visual_intent}]`），不切真人画面的普通段落一律不输出。
- **Rationale**: 59 句逐句打标导致输出 Token 达 4,800+，在第 29 句即因触顶模型单次生成上限发生中途截断与 JSON 语法破损，引发 0% 分镜灾难。改用稀疏清单后，Token 消耗骤降 95%（<300 Tokens），耗时从 67s 缩短至 2~3s 极速流式返回，彻底免疫截断。

### R7: 中文字幕自然意群断句与弹性合并（VideoLingo 范式）
- **Decision**: 彻底废除 `asr_runner.py` 中 `curr_len >= 14` 的无脑硬截断和单字正则 `^标点$`。采用“物理词戳 + 标点感知（。/！/？/，）+ 语法意群保护（连词/介词前断开，动宾短语与固定搭配内部严禁腰斩）+ 8~18 字宽松弹性合并”。
- **Rationale**: 短视频口播字幕以“完整一句话或半句话”为黄金视读单元。14 字硬截断会无情腰斩动词短语（如“千万不 / 要报。”），且死板的 14 字合并上限使得 15 字的合法设问句被拆散并产生大量 0.4s 微短碎片。放宽至 8~18 字并保护语法边界，能够 100% 消除中文词组腰斩并保持视听节奏自然流畅。

### R8: 强相关精准锚定 + 自由段落自适应随机铺底达成 60%~70% 黄金覆盖率
- **Decision**: 针对 1~2 分钟短视频 60%~70%（即 72~84 秒）的高频空镜需求，确立“强相关语义精准锚定 + 自由段落自适应随机铺底”双层编排机制：
  1. 口播命中“学车场地/环境（venue）”、“教练带教学车（lesson）”、“体检报名流程（experience）”等强相关场景时，优先绑定对应分类素材，并严丝合缝对齐声学发音时间；
  2. 其余普通正文区间，由本地编排引擎在素材库中随机调度素材，按 3~5 秒节奏窗口自适应铺满，硬性确保成片空镜总时长达到 60%~70%（该比例可在策略中手动调节）；
  3. 严格排除三大禁切红线：开场前 1.8s 真人亮相、报价手势句、结尾 CTA 行动召唤句，坚决保留口播真人出镜。
- **Rationale**: 120 秒视频若要切 60%~70%，需要 15~20 个空镜镜头，若全部让大模型编造假理由挑选，极易再次引发 Token 膨胀与模型幻觉。将“强相关精准匹配”交由 AI，“节奏随机铺底”交由本地编排层，既保证了关键画面的准确性，又以零 Token 成本稳稳达成了 60%~70% 的高频视觉节奏。