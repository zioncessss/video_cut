# Walkthrough: 真实 Codex Harness 驱动的智能纠错与自然语言剪辑工作台 (002-real-codex-harness)

## 1. 交付概览 (Overview)
本阶段全面淘汰了此前的 Mock 模拟与占位逻辑，成功通过非交互式子进程直接驱动本地 **Codex CLI (`codex exec`)**，实现真实的大模型驾校专业纠错、全能自然语言微调与设置持久化。

---

## 2. 核心完成特性 (Implemented Features)

### I. 真实生产级 Codex CLI 调度与防挂起 (`backend/app/harness_bridge/codex.py`)
- **Windows 管道防挂起**：显式注入 `stdin=asyncio.subprocess.DEVNULL`，彻底解决 Windows 终端下 `Reading additional input from stdin...` 造成的永久卡死问题。
- **纯净消息提取**：通过 `--sandbox read-only --ephemeral -o <temp_file>` 参数，由临时文件直接提取大模型最后一条输出消息，规避 ANSI 控制符与终端日志干扰。
- **超时与平滑降级**：内置 35 秒单次推理超时截断与异常捕获，发生任何不可用情况均平滑回退至 `EmbeddedHarnessBridge` 并明确标记 `harness_engine_used = "codex (fallback embedded)"`。

### II. 驾校垂直领域智能纠错 (`POST /api/v1/editor/correct`)
- 组装包含高频行业专有词库（场地、考场、体检、科目二、倒车入库等）及同音错别字规则的提示词。
- 返回纠偏后的字幕列表与原词/新词对照明细清单（包含修改原因）。
- 前端工作台配备「智能纠错」按钮与高亮对比卡片。

### III. 全能自然语言微调 (`POST /api/v1/instruction/apply`)
- 动态注入当前工程状态（字幕、时间轴、B-roll 切片）与可用素材库元数据（分类、时长、文件名）。
- 支持全能操作意图：
  1. 解说词文案润色改写（如“把第1句开场白润色得热情昂扬”）；
  2. 智能重排与替换空镜素材（如“将第2句画面换成体检分类素材”）；
  3. 剪辑节奏与时间微调。
- 同步应用并返回智能体操作说明与耗时。

### IV. 设置中心持久化与秒级连通性探针 (`POST /api/v1/settings/test-harness`)
- 前端设置页支持切换 Active Harness，并持久化写入 `storage/settings.json`。
- 支持选填 `-m` 模型参数覆盖（留空则继承 `~/.codex/config.toml`）。
- 新增「测试连通性 (Ping)」按钮，实时反馈 Codex CLI 响应延迟（如 `2.8s`）与当前活跃模型。
- 工作台顶部状态栏实时呈现驱动引擎徽标（`Harness: CODEX (GLM-5.3-Flash)` 或 `Harness: 降级 Embedded`）。

---

## 3. 测试与验证结果 (Verification Results)

### 后端自动化测试套件
```powershell
$env:PYTHONPATH='backend'; pytest -v
```
**结果**: 23 个测试用例全部通过 (23 passed, 0 failed)：
- `tests/test_codex_bridge.py`:
  - `test_codex_extract_json` PASSED
  - `test_codex_is_available` PASSED
  - `test_codex_ping_probe` PASSED
  - `test_codex_correct_subtitles` PASSED
  - `test_codex_natural_instruction` PASSED
- `tests/test_editor_api.py`:
  - `test_editor_analyze_and_render_flow` PASSED
  - `test_editor_correct_endpoint` PASSED
  - `test_instruction_apply_endpoint` PASSED
- `tests/test_all_flows.py` PASSED (含 `test-harness` 连通性探针测试)
- `tests/test_zcode_bridge.py` PASSED

### 前端生产构建校验
```powershell
pnpm --prefix frontend run build
```
**结果**: TypeScript 类型检查通过，Vite 打包耗时 2.42s，零报错。
