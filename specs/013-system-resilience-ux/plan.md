# Implementation Plan: 系统安全边界、状态一致性与交互体验加固 (013-system-resilience-ux)

**Branch**: `013-system-resilience-ux` | **Date**: 2026-09-24 | **Spec**: [specs/013-system-resilience-ux/spec.md](file:///d:/project/video_cut/specs/013-system-resilience-ux/spec.md)

**Input**: Feature specification from `specs/013-system-resilience-ux/spec.md` & Audit findings in `security_and_state_audit_report.md`

## Summary

系统性解决 VideoCut 全链路安全边界与交互体验问题：
1. **数据一致性与幽灵消除**：修复 `delete_project_by_material` 磁盘遗留与 `_heal_from_disk` 盲目复活，引入前端 `AbortController` 消除异步竞态；
2. **故障韧性与任务管控**：为 MiniMax ASR 引入指数退避重试，为批量混剪引入取消（Cancel）、单项重试（Retry Failed）与服务启动僵尸批次自愈；
3. **真实等待与阶段感知**：前端连通后端的阶段进度轮询，打造四阶段步骤条（Step Indicator），在批量混剪中渲染真实进度条与错误详情，消除错误吞噬。

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.2+, React 18.2+  
**Primary Dependencies**: FastAPI, Uvicorn, SQLite3, Httpx, Axios, TailwindCSS, Lucide-React, Electron 30  
**Storage**: SQLite (`storage/videocut.db`) 为唯一权威存储，物理磁盘隔离目录（`storage/tasks/`、`storage/materials/`）  
**Testing**: pytest (后端集成与单元测试)、Node/Browser 验证 (前端界面流转)  
**Target Platform**: Windows 10/11 64-bit、macOS (Darwin)  
**Project Type**: Desktop Application (Electron + Python Sidecar/Dev Engine)  
**Performance Goals**: 
- 素材删除物理文件与数据库同步清理耗时 < 100ms；
- 前端阶段轮询间隔 800ms，对系统 CPU 占用率增加 < 0.1%；
- 批量任务取消响应时间 < 500ms。  
**Constraints**: 严格遵守真实运行准则（AGENTS.md），严禁使用假数据替代真实物理任务；不引入庞大的第三方队列系统（如 Celery/Redis），保持单机轻量。

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Compliance Analysis | Status |
| :--- | :--- | :---: |
| **I. C端体验与免终端启动** | 所有任务取消、重试、错误提示完全集成于 GUI，彻底消除后台黑框与无法停止的死锁情况。 | **PASS** |
| **II. Harness 抽象与引擎解耦** | ASR 与大模型重试逻辑收敛于底层 runner 与 client，对外接口协议保持无感与高可用。 | **PASS** |
| **III. 智能音视频管线与声画解耦** | 进度反馈如实映射音视频管线（抽取->ASR->纠偏->分镜->压制），严禁伪造假进度。 | **PASS** |
| **IV. 硬件感知与批处理并发** | 批量混剪增加取消和重试，避免资源被无效死锁批次占用，提升硬件利用率。 | **PASS** |
| **V. 极简高效与防无用循环** | 进度查询复用已有轻量内存字典与短轮询，拒绝 WebSocket/外部消息队列过度工程。 | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/013-system-resilience-ux/
├── spec.md              # 需求规格说明书
├── plan.md              # 本实现计划 (Implementation Plan)
├── research.md          # Phase 0 技术决策与调研报告
├── data-model.md        # Phase 1 数据模型与状态机演进
├── quickstart.md        # Phase 1 端到端验证与测试指南
├── contracts/           # Phase 1 接口与交互契约
└── tasks.md             # Phase 2 实施任务清单 (/speckit-tasks 输出)
```

### Source Code Impact

```text
backend/app/
├── api/
│   ├── editor.py        # 加固 analyze_and_cut 异常回滚，完善 _pipeline_progress 状态同步
│   └── batch.py         # 新增 cancel、retry-failed 接口，优化 items 进度持久化
├── core/
│   └── config.py        # 统一常量与配置检查
├── db/
│   └── repository.py    # 增加批量作业自愈更新接口
├── main.py              # lifespan 启动事件增加僵尸批次巡检自愈
└── native_engine/
    ├── asr_runner.py    # MiniMax ASR 引入 3 次指数退避重试
    ├── project_storage.py # 修复 delete_project_by_material 物理清理，加固 _heal_from_disk
    └── storage.py       # 级联删除安全性强化

frontend/src/
├── pages/
│   ├── VideoEditor.tsx  # 接入 AbortController，接入 800ms 进度轮询，渲染四阶段 Step Indicator，透出真实错误
│   └── BatchCut.tsx     # 渲染子项进度条与错误 Tooltip，接入取消与重试按钮
└── services/
    └── api.ts           # 增加 cancelBatchJob、retryFailedBatchJob 契约，支持 AbortSignal
```

---

## Implementation Outline (Phase-by-Phase)

### Phase 0: 调研与决策确认 (已完成)
- 详见 [`research.md`](file:///d:/project/video_cut/specs/013-system-resilience-ux/research.md)。

### Phase 1: 契约、数据模型与验证指南 (当前阶段)
1. **Data Model**:
   - `BatchJobStatus` 扩展枚举：`CANCELED` ('canceled'), `INTERRUPTED` ('interrupted')；
   - 细化 `PipelineStage` 与前端 UI 步骤的映射关系。
2. **Contracts**:
   - `contracts/progress-api.json`: 进度查询响应模式；
   - `contracts/batch-control-api.json`: 取消批次与重试失败项接口契约。
3. **Quickstart**:
   - 编写重现并验证“幽灵工程消除”、“ASR网络退避”、“取消批次”、“初剪阶段进度条”的验证步骤。
4. **Agent Context Update**:
   - 更新 `AGENTS.md` 的 Spec Kit 引用指向本计划。

### Phase 2: 代码实现 (通过 `/speckit-tasks` 驱动)
- 实施所有后端接口与前端 UI 改造，编写对应的单元与集成测试。
