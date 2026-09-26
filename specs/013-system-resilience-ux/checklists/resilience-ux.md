# Specification Quality Checklist: 系统安全边界、状态一致性与交互体验 (Resilience & UX)

**Purpose**: Validate specification completeness, clarity, consistency, and testability for system resilience, data integrity, error recovery, and long-task UX before implementation  
**Created**: 2026-09-24  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)  
**Domain**: Data Lifecycle Integrity, Failure Recovery, State Sync & Progress UX  
**Audience**: PR Reviewer, System Architect & Feature Author  

---

## 1. 数据生命周期与冲突防范 (Data Lifecycle & Integrity)

- [x] CHK001 需求中删除口播素材（`delete_material`）时，是否明确界定了需物理清理的全部磁盘目录与影子文件清单（包括 `storage/tasks/<task_dir>/`、`project_manifest.json`、`subtitles.ass/srt`、`cover.jpg` 及 `output_*.mp4`）？ [Completeness, Spec §FR-101]
- [x] CHK002 在自愈逻辑（`_heal_from_disk`）中，是否以无歧义的规则规定了当任务清单引用的 `talking_head_id` 在 `materials` 表不存在时，系统必须就地删除该残留目录而非恢复入库？ [Clarity, Spec §FR-102]
- [x] CHK003 是否明确了当空镜素材被删除时，既有工程中引用该素材的字幕片段（`broll_material_id`）与分镜替换项（`broll_replacements`）的数据置空（`SET NULL`）与自动编排补偿规范？ [Completeness, Spec §FR-101, Gap]
- [x] CHK004 需求是否量化了素材删除操作的耗时门槛（例如物理删除与数据库联动清理总体延迟 < 100ms）？ [Measurability, Spec §KPI]
- [x] CHK005 前端防竞态守卫（`AbortController`）是否覆盖了所有素材切换与路由跳转场景，并明确定义了当请求被 Abort 时静默忽略且禁止更新状态与弹窗的规范？ [Coverage, Spec §FR-103]

---

## 2. 故障容错、重试机制与清理韧性 (Failure Recovery & Resilience)

- [x] CHK006 MiniMax 云端 ASR 的重试策略是否明确量化了重试次数上限（3 次）、退避时间梯度（1s, 2s, 4s）以及触发重试的具体错误类型白名单（HTTP 5xx, 429, Timeout, ConnectionReset）？ [Clarity, Spec §FR-201]
- [x] CHK007 需求是否明确规定了当 ASR 重试 3 次仍失败时，已创建的临时音频（`_audio.wav`）与预分配任务目录必须执行即时回滚清理（Rollback Cleanup）？ [Completeness, Spec §FR-201]
- [x] CHK008 大模型纠偏接口在遇到超时或 5xx 错误时，需求是否明确规范了自动平滑降级至“词库确定性纠偏”而非中断抛错的兜底行为？ [Consistency, Spec §FR-201, Plan §Phase 0]
- [x] CHK009 批量混剪取消接口（`POST /batch/jobs/{id}/cancel`）是否清晰定义了正在压制条目与排队中条目的状态跃迁（`canceled`）以及后台子进程资源的回收时限（< 500ms）？ [Measurability, Spec §FR-202]
- [x] CHK010 批量单项重试接口（`POST /batch/jobs/{id}/retry-failed`）是否明确规定了仅重置 `failed` 状态条目，而严格保留已成功（`completed`）项产物不被二次覆盖？ [Consistency, Spec §FR-203]
- [x] CHK011 后端启动自愈逻辑是否明确界定了需被标记为 `interrupted` 的历史状态集合（`running`、`queued`），并规定了向前端透出的中断说明文案？ [Clarity, Spec §FR-204]

---

## 3. 前后端状态同步与阶段跳转 (State Sync & Communication)

- [x] CHK012 前端一键初剪与后端进度更新的轮询契约是否量化了轮询间隔（推荐 800ms）及超时中断阈值（如单视频超过 180s 无响应判定超时）？ [Clarity, Spec §FR-301]
- [x] CHK013 需求是否明确规定了轮询时的查询键值标准（优先使用 `talking_head_id` 直至工程实例生成，生成后切换为 `project_id` 追踪）？ [Consistency, Spec §FR-301, Contract §progress-api]
- [x] CHK014 当长任务 HTTP 请求由于网络断开或弱网导致连接中断时，前端轮询机制是否具备断线重连（Reconnect）与终态拉取恢复能力？ [Edge Case, Spec §Edge Cases, Gap]
- [x] CHK015 批量混剪队列详情拉取是否彻底废除了 `list.slice(0, 10)` 的硬编码截断，确保所有激活批次（非 `finished`）均能获得实时进度轮询？ [Completeness, Spec §FR-302]

---

## 4. 真实交互体验与等待感知 (UX & Progressive Disclosure)

- [x] CHK016 初剪阶段指示器（Step Indicator）是否以无歧义的映射关系绑定了后端的 4 大核心业务阶段（音频抽取 15% → 语音转写 45% → AI专词纠偏 70% → 双层分镜 90% → 完成 100%）？ [Clarity, Spec §FR-301, DataModel §3]
- [x] CHK017 在耗时最长的大模型纠偏阶段，指示器组件是否定义了动态波纹或文本呼吸动效，明确向用户传达“AI 正在推理中”的实时生命体征感知？ [Clarity, Spec §FR-301]
- [x] CHK018 批量混剪卡片在渲染 `running` 状态时，是否明确规定了必须消费并视觉呈现 `item.progress` 进度条与具体百分比数值，而非仅显示静态文字？ [Completeness, Spec §FR-302]
- [x] CHK019 当批量条目或初剪任务失败时，界面是否明确规定必须通过 Tooltip、可折叠抽屉或弹窗如实展示后端返回的真实报错详情（`error` / `detail`），彻底杜绝静态模糊遮掩？ [Clarity, Spec §FR-303]
- [x] CHK020 导出成片压制阶段（Render），界面是否清晰告知了用户当前处于 FFmpeg 复合渲染与硬件编码阶段，并提供动画或预估倒计时提示？ [Coverage, Spec §FR-301, Gap]

---

## 5. 验收准则与可度量性 (Acceptance Criteria & Measurability)

- [x] CHK021 “幽灵工程复活率为 0%”是否具备自动化端到端测试断言进行持续回归验证？ [Measurability, Spec §KPI, Quickstart §Scenario 1]
- [x] CHK022 “ASR 遭遇网络瞬时抖动时自动恢复成功率达到 100%”是否具备可注入 HTTP 502/Timeout 的自动化 Mock 测试场景？ [Measurability, Quickstart §Scenario 2]
- [x] CHK023 “批量混剪任务取消响应延迟小于 500ms”是否明确了性能度量的起止打点标准？ [Measurability, Plan §Performance Goals]
- [x] CHK024 “初剪四阶段进度步进平滑无跳变、无死锁假死”是否具备交互验收的量化指标（各阶段留存显示时长 ≥ 300ms 避免走马灯闪烁）？ [Acceptance Criteria, Spec §FR-301]

---

## Notes

- 本清单作为 `specs/013-system-resilience-ux` 特性需求规格质量的单元测试套件（Unit Tests for Requirements）。
- 在正式进入 `/speckit-tasks` 任务分解与编码实施前，各项需求书写质量必须经由本清单逐项校验通过。
- 每一个 Checklist 事项均带有明确的质量维度标签（`[Completeness]`, `[Clarity]`, `[Consistency]`, `[Measurability]`, `[Coverage]`）与可追溯的文档章节锚点。
