# Phase 0 技术决策与调研报告 (013-system-resilience-ux)

## 1. 调研背景与技术目标

本报告旨在针对系统安全边界、状态一致性与交互体验四大核心问题，提供最简、高鲁棒且不引入过度工程的架构设计决策。

---

## 2. 关键架构决策与技术权衡

### 决策 1：幽灵工程复活根除与素材级联清理策略
* **选择方案**：双重防御——`delete_project_by_material` 主动清理物理任务目录 + `_heal_from_disk` 强制外键真实性守卫。
* **技术原理**：
  1. 在 `ProjectStorageService.delete_project_by_material(talking_head_id)` 中，先通过 `get_by_material_id` 获取工程对象，在删除 SQLite 记录前调用统一清理函数 `_cleanup_project_files(p)`，使用 `shutil.rmtree` 彻底移除 `storage/tasks/<task_dir>/` 及 `project_manifest.json`；
  2. 在 `_heal_from_disk()` 中，增加前置守卫：从 SQLite 查询当前有效 `talking_head_id` 集合；若 manifest 中的 `talking_head_id` 已不在集合中，直接判定为孤儿残余垃圾，执行物理删除且严禁入库。
* **为什么选择此方案**：
  * **高可靠**：即使未来发生外部手动修改或意外崩溃，启动自愈也不会错拉已被删除的资产；
  * **轻量级**：完全基于现有 `ProjectStorageService` 现有函数组合，无需修改 SQLite 基础表结构。
* **否决的替代方案**：
  * *替代方案 A：在 SQLite 中直接开启全局外键 CASCADE 级联* —— 否决原因：SQLite 的 `ON DELETE CASCADE` 只能删除数据库表行，无法触发 Python 层的磁盘物理文件 `shutil.rmtree`，依然无法阻止 `_heal_from_disk()` 扫描磁盘清单而复活。
  * *替代方案 B：彻底废除 `_heal_from_disk()` 机制* —— 否决原因：`_heal_from_disk()` 是断电与历史数据迁移的关键自愈通道，彻底删除会导致意外崩溃时未保存的成片丢失。

---

### 决策 2：云端 ASR 请求的指数退避重试 (Exponential Backoff)
* **选择方案**：基于 Python 标准异步/同步退避逻辑（或 Tenacity 轻量装饰器），针对瞬时网络故障（HTTP 500/502/503/504、429 Too Many Requests、网络超时）执行最多 3 次指数退避重试（1s, 2s, 4s）。
* **技术原理**：
  在 `ASRRunner.transcribe_minimax` 中，对网络请求部分封装为独立子函数：
  ```python
  retries = 3
  backoff = 1.0
  for attempt in range(retries):
      try:
          res = httpx.post(...)
          res.raise_for_status()
          break
      except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
          if attempt == retries - 1:
              raise
          time.sleep(backoff)
          backoff *= 2.0
  ```
* **为什么选择此方案**：
  * 零新依赖，标准库级别实现；
  * 解决现实中 95% 以上因临时路由抖动导致的偶发报错。
* **否决的替代方案**：
  * *替代方案 A：发生错误时静默降级为本地 Whisper* —— 否决原因：违反 AGENTS.md 准则与系统现实（本地 Whisper 已停用，且若无模型会导致更大崩溃）。

---

### 决策 3：前端异步长任务与防竞态守卫 (AbortController)
* **选择方案**：在 `VideoEditor.tsx` 中使用 `useRef<AbortController | null>` 管理进行中的长耗时请求（初剪与工程加载）。
* **技术原理**：
  当用户切换素材 ID（`selectedThId`）或重新点击初剪时：
  ```typescript
  if (abortControllerRef.current) {
    abortControllerRef.current.abort();
  }
  const controller = new AbortController();
  abortControllerRef.current = controller;
  // 将 controller.signal 传入 axios 请求
  ```
  在 catch 块中，如果 `axios.isCancel(err)` 则静默忽略，不更新任何状态与弹窗。
* **为什么选择此方案**：
  * 浏览器与 Axios 标准规范原生支持；
  * 从根本上消除用户快速切换素材时，前序长任务返回冲刷当前视图的 Race Condition。

---

### 决策 4：初剪阶段指示器与真实进度感知机制
* **选择方案**：前端基于轻量轮询驱动 + 状态机 Step Indicator（4 阶段步骤条）。
* **技术原理**：
  1. 后端已经具备现成的 `GET /api/v1/projects/{target_id}/progress` 接口及 `_set_progress` 字典；
  2. 前端在点击“智能初剪与纠偏”后，除了发出 POST 请求外，开启一个 800ms 的 `setInterval` 定时轮询 `fetchProjectProgress(selectedThId)`；
  3. 当获取到后端阶段（`audio_extracting`、`asr_transcribing`、`llm_correcting`、`scene_deciding`、`completed`）时，实时更新页面的 Step Indicator 视觉进度与文字提示；
  4. POST 请求 Resolve 或 Reject 时，清理轮询定时器。
* **为什么选择此方案**：
  * **复用已有后端基建**：无需引入复杂的 WebSocket 服务端通道，零额外通信依赖；
  * **开发成本极低、稳定性极高**：800ms 轮询对单机 127.0.0.1 性能消耗几乎为 0。

---

### 决策 5：批量混剪任务取消、单项重试与僵尸批次自愈
* **选择方案**：
  1. **取消机制**：`batch.py` 中将每一个运行中的 `worker` 映射为 `asyncio.Task` 保存在内存中。新增 `POST /batch/jobs/{id}/cancel`，遍历取消对应 Task 并将 job/item 置为 `canceled`；
  2. **单项重试**：新增 `POST /batch/jobs/{id}/retry-failed`，筛选出 `status == 'failed'` 的 item，重置状态为 `queued` 并调用 `_execute_job` 恢复执行；
  3. **重启自愈**：后端启动时在 `lifespan` 中执行一次 SQL 更新：
     `UPDATE batch_jobs SET status = 'interrupted' WHERE status IN ('running', 'queued')`。
* **为什么选择此方案**：
  * 彻底终结混剪死锁，提供完整的任务生命周期闭环。
