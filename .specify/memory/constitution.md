<!-- Sync Impact Report:
- Version change: Initial Template → 1.0.0
- Ratified: 2026-09-15
- Core principles established:
  1. Desktop C-End Experience & Zero-Terminal Launch
  2. Harness Abstraction & Engine Decoupling
  3. Smart Multi-Track A/V Pipeline (ASR + LLM Correction + B-roll J/L Cut)
  4. Hardware-Aware Concurrency & Batch Resource Optimization
  5. Simplicity, Readability & No Wasteful Loops
- Added sections: UI/UX Aesthetic & Routing Standards, Quality & Extensibility Gates
-->

# VideoCut Harness Web 宪章 (Constitution)

## Core Principles

### I. C端体验与免终端启动 (Zero-Terminal Launch)
面向 C 端非技术用户设计，软件严禁依赖命令行或终端交互作为启动与常规操作入口。
- 必须原生适配 Windows 与 macOS 双端一键启动机制（通过桌面封装/轻量应用壳）。
- 错误信息与运行状态全部通过图形界面友好呈现，禁止弹出未捕获的终端黑框或崩溃堆栈。

### II. Harness 抽象与引擎解耦 (Harness Abstraction & Decoupling)
业务逻辑与底层执行器彻底解耦。
- 针对 codex、zcode 及本地自定义 harness，定义统一的适配层接口（Adapter Interface）。
- Web 前端只与抽象的 Harness API 交互，底层 harness 的切换、升级或替换不影响前端操作交互与剪辑业务流。

### III. 智能音视频管线与声画解耦 (Smart Multi-Track A/V Pipeline)
核心剪辑业务聚焦于“口播原声保留 + 语义空镜智能切入（J/L-Cut）”。
- **ASR + LLM 双重校验**：口播视频提取音频后进行语音转文字，必须经由 LLM 语义校正同音错别字与断句后方可生成最终字幕。
- **关键词驱动空镜替换**：基于校正后的文字时间轴匹配业务关键词（地点/价格/教练/体检/教学），在保留口播音轨的前提下将对应时间区间的画面平滑替换为目标分类素材（初版支持同类随机选取）。
- **可逆与可微调**：所有自动生成的切片区间与字幕文本均必须允许用户在界面二次编辑与微调。

### IV. 硬件感知与批处理并发调度 (Hardware-Aware Batch Concurrency)
批量剪辑是核心生产力场景，必须防止算力耗尽导致的系统卡死或视频合成崩溃。
- 系统在启动批量合成前必须估算当前硬件资源（CPU 核心数、内存剩余、GPU/硬件加速可用性）。
- 动态调整并发作业数（Concurrency Throttling），提供清晰的队列进度与资源占用可视化反馈。

### V. 极简高效与防无用循环 (Simplicity, Readability & No Wasteful Loops)
遵循资深工程实践，拒绝过度工程。
- 业务代码直截了当，以功能可靠实现为主，代码保持高可读性与短链路。
- 严格杜绝无意义的嵌套轮询、空转死循环与不必要的深层抽象。

---

## UI/UX 设计与路由规范

### 1. 视觉风格 (Visual Aesthetic)
- 全局采用 **浅色调（Clean Light Mode）**，以高质感白色、柔和浅灰为底，辅以克制而现代的主题强调色（如活力蓝/薄荷绿）。
- 界面组件注重层次、阴影细腻、留白舒适，具备现代 AI 原生产品的网感与专业质感。

### 2. 路由与功能分区 (Clear Routing & Layout)
- 路由结构清晰明确：
  - `/upload`（素材库与分类上传：口播、场地、体检、教学）
  - `/editor`（剪辑工作台：左侧视频带字幕播放器，右侧时间轴字幕可编辑列表，底部文本/调整输入框）
  - `/batch`（批量生产与任务队列管理）
  - `/settings`（Harness 引擎切换与硬件资源参数配置）

---

## 质量与扩展性保障 (Quality & Extensibility Gates)

1. **素材分类物理规范**：素材上传按固定物理目录隔离存储（`talking_head/`, `venue/`, `medical/`, `lesson/`），保持目录结构纯净与检索高效。
2. **FFmpeg 指令结构化组装**：音视频复合滤镜（filter_complex）通过结构化代码组装，必须具备参数合法性校验。
3. **跨平台兼容测试**：所有路径处理必须使用跨平台标准 API（支持 Windows 反斜杠与 Unix 斜杠兼容）。

---

## 治理规范 (Governance)

- 本宪章为 `video_cut` 项目的最高开发与架构准则，后续所有需求规格、技术方案与任务实现均受此约束。
- 宪章修改遵循语义化版本规则（MAJOR/MINOR/PATCH），重大架构调整需经评审后递增版本号并同步受影响模板。

**Version**: 1.0.0 | **Ratified**: 2026-09-15 | **Last Amended**: 2026-09-15
