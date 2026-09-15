# Feature Specification: 真实 Codex Harness 驱动的智能纠错与自然语言剪辑工作台 (Real Codex Harness Video Cut Bridge)

**Feature Branch**: `002-real-codex-harness`  
**Created**: 2026-09-15  
**Status**: Ready for Planning / Implementation  
**Target Delivery**: 接入真实 Codex CLI，淘汰 Mock 模拟，实现真实的驾校专有词 LLM 纠偏、全能自然语言微调、设置持久化与引擎状态感知。

---

## 1. 业务背景与定位 (Context & Vision)

在 Spec 001 中，系统搭建了双核混合架构（Native Engine + Harness Bridge）及原型前端。但原有的外部引擎调用为 Mock 降级模拟。  
为了让用户直观体验智能体（Harness）套壳带来的高阶能力，本阶段聚焦将 **Codex CLI (`codex exec`)** 真正做真：
1. **真实 Codex CLI 调度**：通过本地非交互式 `codex exec` 子进程调用，依托本地配置的模型（如 GLM-5.3-Flash 或自定义覆盖）进行高阶认知推理。
2. **驾校垂直领域智能纠错**：利用大模型结合驾校上下文与专有词库，对 ASR 口播字幕进行语法、同音字及专业术语纠偏，返回结构化更新及改动原因清单。
3. **全能自然语言微调**：底部自然语言输入框支持“改写/润色文案”、“根据素材库重新分配 B-roll 空镜”、“按秒微调时间戳与剪辑节奏”，并自动同步应用到工程状态。
4. **设置持久化与可视化感知**：前端设置中心支持持久化保存选定 Harness 与可选模型名称（`-m`），具备「测试连通性」秒级探测能力，剪辑页实时展示当前驱动引擎与降级状态。

---

## 2. 用户场景与测试用例 (User Stories & Acceptance)

### User Story 1 - 设置中心持久化与 Codex CLI 连通性测试 (Priority: P1)
作为系统管理员或运营人员，我希望在设置页选择 Codex 作为主力 Harness，并能即时测试其 CLI 连通性与活跃模型，避免配置错误导致运行失败。

- **独立验证方式**：在前端设置页选择「Codex Harness」，填写可选模型名称，点击「测试连通性」，观察即时返回的延迟与模型信息，刷新页面验证设置已持久化。
- **验收场景**：
  1. **Given** 处于设置中心，**When** 点击「测试连通性」，**Then** 后端执行最小探针 `codex exec --sandbox read-only --ephemeral`，2-5 秒内返回成功状态、响应耗时（如 `1.8s`）和检测到的模型名称。
  2. **Given** 用户切换 `active_harness` 为 `codex` 并保存，**When** 重启后端服务或刷新页面，**Then** 配置保持生效且存储于 `storage/settings.json`。

---

### User Story 2 - 真实 Codex CLI 口播字幕智能纠错 (Priority: P1)
作为驾校短视频创作者，我希望点击「智能纠错」后，系统调用真实 Codex CLI 对口播 ASR 字幕进行上下文与驾校专有词纠偏，并直观展示修改前后对比与替换原因。

- **独立验证方式**：导入含有错别字（如“科尔教练打方盘”、“五万平米的特产”、“去一二零体检车”）的字幕，点击智能纠错，验证返回更新后的标准文字（“科目二教练打方向盘”、“五万平米的考场”、“去体检车”），并在前端显示高亮变更。
- **验收场景**：
  1. **Given** 编辑器中存在待校正字幕，**When** 点击「智能纠错」，**Then** 后端组装 Prompts 与驾校专有词库，通过 `codex exec` 获取结构化纠偏结果。
  2. **Given** Codex 返回纠正数据，**When** 前端接收到结果，**Then** 字幕列表自动同步更新，且弹出/展示纠错改动卡片列表（包含原始词、纠正词、修改理由），支持一键审阅。
  3. **Given** Codex CLI 发生超时（>30s）或异常，**When** 触发纠错，**Then** 平滑降级至内置 Embedded 引擎，返回本地规则纠偏结果并带有“已降级为内置引擎”明确提示。

---

### User Story 3 - 全能自然语言微调（改写/空镜替换/节奏微调） (Priority: P1)
作为视频剪辑师，我希望在底部微调输入框输入自然语言指令（如“把第一句改得更激动一点”、“把涉及场地的镜头全换成体检素材”、“前两句稍微加快0.3秒”），Codex 能够解析意图并直接调整工程工程参数。

- **独立验证方式**：在输入框输入上述指令，验证工程工程中的字幕文本、时间戳或 B-roll 关联的 `material_id` 发生符合意图的精确变更。
- **验收场景**：
  1. **Given** 当前视频工程包含若干字幕与空镜绑定，**When** 用户输入“把开场白改成热情欢迎新学员的口号”，**Then** Codex 生成润色后文本并更新第 1 句字幕。
  2. **Given** 用户输入“把第 2 句空镜换成 medical 分类的体检素材”，**When** 下发微调指令，**Then** Codex 从素材元数据列表中筛选出合适素材 ID 并替换对应 BrollReplacement。
  3. **Given** 用户输入“微调节奏”，**When** 指令生效，**Then** 返回详细的操作解释（explanation）并在界面通知栏提示。

---

### User Story 4 - 剪辑工作台引擎状态可视化感知 (Priority: P2)
作为用户，我需要在剪辑主界面清楚知道当前操作是由真正的 Codex CLI 大模型处理，还是处于内置降级模式，具备透明的可信度。

- **独立验证方式**：在工作台顶部状态栏或微调卡片旁，查看状态徽章。
- **验收场景**：
  1. **Given** 当前生效为 Codex 且连通正常，**Then** 界面显示绿色徽章 `Harness: Codex (Active)`。
  2. **Given** 触发降级或未安装 Codex，**Then** 界面显示黄色徽章 `Harness: Embedded (Fallback)`。

---

## 3. 技术约束与集成考量 (Constraints & Principles)

1. **子进程通信防范（核心避坑）**：
   - Windows 环境下 `codex exec` 默认会读取标准输入（stdin），若未关闭管道会导致子进程挂起等待。必须显式设置 `stdin=asyncio.subprocess.DEVNULL`。
   - 使用 `--sandbox read-only --ephemeral -o <temp_file>` 参数执行，直接将大模型最后一条输出消息写入临时文件并解析 JSON，避免 ANSI 控制字符与流式终端日志干扰。
2. **超时与降级保证**：
   - 每次 CLI 调用设置 35 秒上限超时 `asyncio.wait_for(...)`，超时或非零退出码自动调用 `EmbeddedHarnessBridge` 降级，保障业务零阻塞。
3. **设置隔离与安全性**：
   - 模型参数 `-m` 仅支持安全字符（防命令注入），持久化写入 `storage/settings.json`。