# Phase 0 Research: 真实 Codex Harness 桥接器与指令微调技术调研

## 1. 调研背景与技术目标
在 Spec 001 中，`CodexHarnessBridge` 仅包含降级至本地内置规则引擎的占位逻辑。本阶段核心目标是让后端直接驱动用户本机的 `codex` 命令行（Codex CLI v0.150.1+），实现真实的大模型推理、语义纠偏、文本润色与编排微调。

## 2. 核心技术决策与验证

### 决策 1: Codex CLI 进程调用与通信机制
- **选型方案**: 采用 Python `asyncio.create_subprocess_exec` 执行 `codex exec --sandbox read-only --ephemeral -o <temp_file> <PROMPT>`。
- **验证结果**:
  - 实测耗时：在本地 127.0.0.1:15721 代理及 GLM-5.3-Flash 驱动下，单次非交互式执行耗时仅 2.5 ~ 4.5 秒。
  - 管道挂起防范：Windows 环境下若未断开 stdin 管道，`codex exec` 会持续输出 `Reading additional input from stdin...` 从而无限挂起。因此必须显式传入 `stdin=asyncio.subprocess.DEVNULL`。
  - 干净输出提取：通过 `-o <temp_file>` 参数让 Codex CLI 仅将 Agent 的最终回复写入临时文件，完美规避 stdout 中的 ANSI 控制符、进度日志与 session 标头。

### 决策 2: 结构化 JSON 提示词工程 (Prompt Engineering)
- **选型方案**:
  - 在 Prompt 中注入驾校垂直领域专有词典（场地、体检、科目二、倒车入库等）、当前字幕时间轴及素材元数据。
  - 强制要求 Codex 仅输出单行或合法的 JSON 代码块，并在后端设计双层解析机制：
    1. 优先尝试直接 `json.loads(text)`。
    2. 若大模型输出包含 ```json ... ``` markdown 包装，通过正则自动提取内部纯 JSON 载荷。
- **容错设计**:
  - 若解析失败或超时（超过 35s），自动回退至 `EmbeddedHarnessBridge`，确保前端页面永远不会处于卡死或白屏状态。

### 决策 3: 设置持久化与连通性探针
- **选型方案**:
  - 持久化介质：`storage/settings.json`，结构包含 `active_harness`、`llm_model`（可选覆盖 `-m`）、`updated_at`。
  - 连通性探针：新增接口 `POST /api/settings/test-harness`，下发最小 Prompt `Output exact JSON: {"ping": "pong"}`，测量往返耗时（RTT）并捕获当前实际生效的模型版本。

### 决策 4: 自然语言全能微调意图落地
- **选型方案**:
  - 用户输入微调指令（如“把第1句文案润色为热烈迎新”、“把第2句画面换成体检素材”、“将前两句语速稍微加快”）。
  - Prompt 注入：
    1. `current_subtitles`: 当前所有字幕片段及时间戳。
    2. `available_materials`: 当前系统中所有已就绪素材库元数据（ID、分类、时长、文件名）。
    3. `user_instruction`: 用户的自然语言指令。
  - Codex 返回操作响应：
    ```json
    {
      "explanation": "已将第1句文案调整为热情开场白，并将第2句关联的空镜素材替换为体检分类素材",
      "updated_subtitles": [...],
      "updated_brolls": [...]
    }
    ```
  - 后端合并应用并直接同步回传前端，前端即时刷新时间轴与预览。