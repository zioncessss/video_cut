# Quickstart & Verification: 真实 Codex Harness 驱动验证指南

本指南指导开发者与测试人员如何端到端验证真实 Codex CLI 的连通性、智能纠错、自然语言微调与持久化设置。

## 1. 前置准备 (Prerequisites)
- 确保本地已安装 `codex-cli`（可执行命令 `codex --version` 验证输出 `codex-cli ...`）。
- 确保本地代理（如 `http://127.0.0.1:15721/v1`）或默认 Codex LLM 上游处于在线可用状态。
- 进入项目根目录：
  ```powershell
  cd d:\project\video_cut
  ```

## 2. 后端测试用例执行 (Automated Unit & Integration Tests)
执行 Codex 桥接器专有测试套件，验证子进程通信、JSON 提取、超时降级及设置持久化：
```powershell
pytest tests/test_codex_bridge.py -v
```

**预期结果**：
- `test_codex_ping_success`: Codex CLI 探针返回 success=True，检测出活跃模型，延迟低于 10 秒。
- `test_codex_correct_subtitles`: 能够精准将带有同音错字的驾校字幕纠偏为“科目二”、“打方向盘”，并附带纠错明细。
- `test_codex_natural_instruction`: 能够解析“把文案润色”与“切换体检素材”的自然语言微调指令，返回结构化更新方案。
- `test_codex_timeout_fallback`: 模拟异常或超时场景下，无缝降级为 EmbeddedHarnessBridge 并标记 `harness_engine_used = "codex (fallback embedded)"`。

## 3. Web 界面端到端验证 (Manual E2E Flow)

### 步骤 1: 启动前后端服务
```powershell
# 启动后端
python backend/app/main.py

# 启动前端
cd frontend; pnpm dev
```

### 步骤 2: 设置中心连通性验证
1. 浏览器访问 `http://localhost:5173/settings`。
2. 在「Active Harness」选择 `codex`。
3. 点击「测试连通性」按钮。
4. **验证**：按钮出现加载状态，并在 3 秒左右提示“Codex 连通成功，延迟: 2.8s，模型: glm-5.3-flash”。
5. 点击「保存设置」，刷新页面，验证配置已持久化保持在 `codex`。

### 步骤 3: 剪辑工作台智能纠错验证
1. 访问 `http://localhost:5173/editor`。
2. 观察界面右上角或顶部状态栏，确认显示绿色徽章 `Harness: Codex`。
3. 在右侧字幕编辑列表中，输入或导入包含“科尔考场”、“打方盘”的片段。
4. 点击「智能纠错」按钮。
5. **验证**：文字自动纠正为“科目二考场”、“打方向盘”，同时弹出高亮变更卡片，列出修改原因。

### 步骤 4: 底部自然语言微调验证
1. 在工作台底部自然语言微调输入框输入：“把第一句开场白改得更有网感和号召力”。
2. 点击「发送指令」或回车。
3. **验证**：字幕第 1 句被大模型润色改写，界面弹出 Toast 提示操作成功，并显示智能体的操作说明。