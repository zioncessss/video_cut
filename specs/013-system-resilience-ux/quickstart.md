# Phase 1 验证指南与端到端运行手册 (013-system-resilience-ux)

## 1. 验证目标

通过可执行的测试场景与用户旅程，验证系统安全边界加固、幽灵工程消除、失败重试与长任务交互体验升级成果。

---

## 2. 自动化端到端测试场景 (Automated Test Scenarios)

### 场景 1：素材删除物理清理与杜绝幽灵复活
* **目标**：验证素材删除时级联清除物理任务目录，且应用自愈时不再恢复该工程。
* **执行命令**：
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
  pytest tests/test_ghost_project_elimination.py -v
  ```
* **期望结果**：
  1. 创建口播素材并执行初剪，产生 `storage/tasks/<task_dir>/project_manifest.json`；
  2. 调用 `storage_service.delete_material(th_id)`；
  3. 断言任务物理目录已从磁盘彻底删除；
  4. 触发 `ProjectStorageService._heal_from_disk()`；
  5. 断言 SQLite 中无幽灵复活记录。

### 场景 2：MiniMax ASR 瞬时网络故障指数退避重试
* **目标**：验证当云端 ASR 遭遇 502/Timeout 偶发异常时能够自动重试成功。
* **执行命令**：
  ```powershell
  pytest tests/test_asr_retry.py -v
  ```
* **期望结果**：
  1. Mock ASR 第一次返回 HTTP 502，第二次返回正常 JSON；
  2. 验证 `transcribe_minimax` 触发重试并在第 2 次成功返回，剪辑链路不崩溃。

### 场景 3：批量混剪中途取消与失败项重试
* **目标**：验证批量作业的生命周期控制接口。
* **执行命令**：
  ```powershell
  pytest tests/test_batch_lifecycle_control.py -v
  ```
* **期望结果**：
  1. 提交包含 4 个条目的批处理作业；
  2. 调用 `POST /batch/jobs/{id}/cancel`，断言状态变更为 `canceled`，排队中的任务被安全终止；
  3. 人工将某项置为 `failed`，调用 `POST /batch/jobs/{id}/retry-failed`，断言仅失败项重新置为 `queued` 并恢复处理。

---

## 3. 手工与前端交互验证场景 (Manual UI Walkthrough)

### 场景 4：一键初剪 4 阶段进度条与阶段感知
1. 打开应用，进入“剪辑工作台” (`/editor`)；
2. 选择一个未剪辑的口播素材，点击 **「⚡ 智能初剪与纠偏」**；
3. **观察交互反馈**：
   * 顶部或居中浮现阶梯式步骤条：
     * `[抽取音频 15%]` → 绿色高亮完成
     * `[语音识别 45%]` → 正在进行
     * `[AI专词纠偏 70%]` → 正在校对
     * `[双层分镜 90%]` → 正在编排
   * 页面不再卡死在单一静态文字上，进度条伴随真实执行阶段步进，直至 100% 自动就绪。

### 场景 5：快速切换素材时的竞态防护 (AbortController)
1. 在左侧素材列表快速连续点击“素材 A”和“素材 B”；
2. 观察控制台网络面板（DevTools Network）：素材 A 的请求被标记为 `canceled`；
3. 素材 B 页面正常加载，不会被素材 A 的延迟返回覆盖。
