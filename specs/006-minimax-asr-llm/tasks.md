# Tasks: MiniMax 统一接管 ASR 与智能剪辑 (006-minimax-asr-llm)

**Input**: Design documents from `specs/006-minimax-asr-llm/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md

## Format: `[ID] [P?] [Story] Description`
- **[P]**: 可并行执行任务（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事标签（[US1], [US2], [US3]）
- 描述中均包含精确文件路径

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 依赖确认与基础环境就绪

- [x] T001 检查并更新 backend/requirements.txt 确保包含 `httpx>=0.26.0` 依赖库

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 基础数据结构与配置层扩展，所有用户故事的前置依赖

- [x] T002 在 backend/app/models/entities.py 中新增 `ASRProvider` 枚举（`minimax`, `local`），并在 `EngineSettings` 与 `SettingsResponse` 模型中增加 `asr_provider` 字段
- [x] T003 [P] 更新 backend/app/core/config.py，增加从 storage/settings.json 获取 `asr_provider`、`minimax_api_key` 与 base_url 的解析逻辑及缺省配置

**Checkpoint**: 基础配置与实体就绪，可以开始各用户故事的开发

---

## Phase 3: User Story 1 - MiniMax 极速语音识别接入与时间戳对齐 (Priority: P1) 🎯 MVP

**Goal**: 通过 MiniMax `asr-1.0` 接口实现 2~4 秒极速转写，获得毫秒级字时间戳并接入既有 6~12 字意群切分，具备本地 faster-whisper 离线降级保底

**Independent Test**: 上传一段 60 秒音频，在配置 MiniMax Key 时 3~5 秒内返回完整字幕与逐字时间戳；断网或 Key 无效时自动回退本地 faster-whisper

### Tests for User Story 1 ⚠️

- [x] T004 [P] [US1] 新建 tests/test_minimax_asr.py：测试 MiniMax 返回的逐字 `segments` 正确转换为系统统一 `words: [{word, start, end}]`，测试网络超时/鉴权失败时自动降级到本地 Faster-Whisper

### Implementation for User Story 1

- [x] T005 [US1] 在 backend/app/native_engine/asr_runner.py 中实现 `transcribe_minimax(audio_path: Path, api_key: str, base_url: str) -> Dict[str, Any]`：以 `multipart/form-data` 请求 `https://api.minimaxi.com/v1/speech_to_text`（指定 `model="asr-1.0"`, `response_format="verbose_json"`, `timestamp_level="word"`），解析各字符起止时间
- [x] T006 [US1] 在 backend/app/native_engine/asr_runner.py 的 `transcribe` 主入口中增加智能路由与异常捕获降级：配置 MiniMax 时优先调用云端转写，超时（timeout=60.0s）或错误时自动平滑回退至本地 faster-whisper
- [x] T007 [US1] 运行 `pytest tests/test_minimax_asr.py` 验证 MiniMax 时间戳提取与离线降级单测全绿

**Checkpoint**: MiniMax ASR 极速转写与时间戳对齐独立可用，离线降级完备 → US1 (MVP) 可验收

---

## Phase 4: User Story 2 - MiniMax 统一接管字幕纠偏与分镜决策 (Priority: P1)

**Goal**: 统一将 Tier A 纠偏与 Tier B 分镜决策的大模型大脑指向 `MiniMax-Text-01`，保证提示词兼容与结构化 JSON 稳定输出

**Independent Test**: 提供含有错字与特定驾校术语的字幕列表，调用纠偏与分镜接口，断言 MiniMax-Text-01 正常输出规范 JSON

### Tests for User Story 2 ⚠️

- [x] T008 [P] [US2] 在 tests/test_api_engine.py 中补充 MiniMax 厂商响应契约测试用例，断言在 OpenAI 兼容格式下 MiniMax-Text-01 正常被识别与消费

### Implementation for User Story 2

- [x] T009 [US2] 在 backend/app/harness_bridge/api_engine.py 与 llm_client.py 中完善对 MiniMax-Text-01 的兼容性保障（包括 base_url 路径补全、JSON 字符串提取与 markdown 代码块解包容错）
- [x] T010 [US2] 验证全链路剪辑：运行 `pytest tests/test_editor_api.py tests/test_scene_decision.py`，确认字幕纠偏与分镜决策在 MiniMax 协议下稳定执行

**Checkpoint**: 文本大模型全链路闭环，Tier A 与 Tier B 顺利运行在 MiniMax 之上 → US2 独立可验收

---

## Phase 5: User Story 3 - 设置中心 MiniMax 统一凭据配置与连通性检测 (Priority: P2)

**Goal**: 用户在前端设置页一处录入 MiniMax API Key，即可同时生效 ASR 与 LLM，支持一键双通道连通性测试，绝不外露明文 Key

**Independent Test**: 在设置页输入 MiniMax Key 点击保存并测试，断言界面弹出双通道就绪成功反馈，且刷新后密钥不以明文显示

### Tests for User Story 3 ⚠️

- [x] T011 [P] [US3] 在 tests/test_settings_api.py 中增加 `/api/v1/settings/test-connection` 连通性探测端点测试与凭据掩码断言（无明文 Key 泄漏）

### Implementation for User Story 3

- [x] T012 [US3] 在 backend/app/api/settings.py 中实现 `POST /api/v1/settings/test-connection` 端点：向 MiniMax Chat 与 STT 发送轻量探针，返回双通道健康状态与延迟；更新 `GET /settings` 与 `PUT /settings` 支持 `asr_provider` 字段
- [x] T013 [P] [US3] 在 frontend/src/services/api.ts 中增加 `testMiniMaxConnection` 接口定义与 `asr_provider` 类型字段
- [x] T014 [US3] 在 frontend/src/pages/Settings.tsx 中重构 API 引擎设置区：增加 MiniMax 预设选项、ASR 模式切换开关（MiniMax 云端极速 / 本地 Whisper）、以及「测试 MiniMax 连通性」操作按钮与状态提示

**Checkpoint**: 设置中心交互与凭据安全完备 → US3 独立可验收

---

## Phase 6: Polish & E2E Validation

- [x] T015 前端代码执行 `pnpm build` 确认零 TypeScript 报错、编译打包顺利通过
- [x] T016 运行全量回归单测 `pytest tests/` 确认全套测试绿色通过
- [x] T017 按照 specs/006-minimax-asr-llm/quickstart.md 验证全场景流转并核查凭据安全红线

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
  └→ Phase 2 Foundational (T002, T003)
       ├→ Phase 3 US1 (MiniMax ASR 极速语音识别: T004~T007) 🎯 MVP
       ├→ Phase 4 US2 (MiniMax LLM 纠偏与分镜: T008~T010)
       └→ Phase 5 US3 (设置中心与连通性检测: T011~T014)
            └→ Phase 6 Polish & 回归验证 (T015~T017)
```

### Parallel Opportunities

- T002 与 T003 可以并行编写；
- US1、US2、US3 的测试用例（T004, T008, T011）可并行先行起草；
- US3 中前端 `api.ts`（T013）与后端端点（T012）可并行开发。