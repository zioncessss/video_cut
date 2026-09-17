# Implementation Plan: 架构迁移至 Electron、SQLite 存储与 Windows/macOS 双端打包发布

**Branch**: `004-electron-sqlite-cross-build` | **Date**: 2026-09-16 | **Spec**: [specs/004-electron-sqlite-cross-build/spec.md](file:///d:/project/video_cut/specs/004-electron-sqlite-cross-build/spec.md)

---

## 1. Summary

将现有的 Web 前后端应用重构并封装为原生的 Electron 跨平台桌面端应用：
1. **构建体系**：采用现代化 `electron-vite` 集中管理 Main/Preload/Renderer 进程，使用 `electron-builder` 实现开箱即用打包。
2. **存储体系**：由分散的 JSON 文件升级为统一的 SQLite 本地数据库（`videocut.db`，开启 WAL 高性能并发模式），实现素材、工程、字幕、策略与全局配置的结构化管理及平滑迁移。
3. **双端打包体系**：
   - Windows 开发宿主机支持本地一键构建 Windows 安装包 (`.exe`) 与 macOS 应用包 (`.zip`)。
   - 接入 GitHub Actions 矩阵流，利用云端 macOS 原生环境自动化产出 `.dmg` 和全架构安装包，并借助本地已安装的 `gh.exe` (GitHub CLI) 实现一键发包。
4. **macOS 免证书安全绕过方案**：配置 Ad-Hoc 自签名与配套的 `一键解除Mac拦截.command` 自动化脚本，绕过苹果 Gatekeeper Quarantine 拦截，无需购买 $99 苹果开发者证书。

---

## 2. Technical Context

- **Language/Version**: TypeScript 5.3+, Node.js 18+, Python 3.11
- **Primary Dependencies**:
  - Desktop: `electron` (v30+), `electron-vite` (v2+), `electron-builder` (v24+)
  - Frontend: React 18, Tailwind CSS, Lucide Icons, Axios, Vite 5
  - Backend/Engine: FastAPI, Uvicorn, faster-whisper, FFmpeg, Python `sqlite3`
- **Storage**: SQLite 3 (`videocut.db`, WAL 模式)
- **Testing**: `pytest` (后端算力与数据库测试), `vitest` / TypeScript 类型检查
- **Target Platform**: Windows 10/11 (x64), macOS 12+ (Apple Silicon arm64 & Intel x64)
- **Project Type**: Desktop Application (Electron Hybrid Client + Native Engine)
- **Performance Goals**: 窗口启动冷开 <1.5s，工程加载 <10ms，双击即用无需终端黑框

---

## 3. Constitution Check

| 宪章核心原则 | 检验要求 | 符合性评估 | 处置措施 |
| :--- | :--- | :--- | :--- |
| **I. C端体验与免终端启动** | 严禁依赖终端或命令行启动，桌面一键启动并自动拉起算力引擎 | **完全符合** | Electron 主进程内部隐式守护拉起后台引擎，对外暴露统一桌面图标 |
| **II. Harness 抽象与解耦** | Web 前端只与抽象 Harness API 交互 | **完全符合** | 渲染层仍通过标准化 API/IPC 协议通信，底层解耦不受影响 |
| **III. 智能音视频管线** | ASR + LLM 真实纠偏 + J/L-Cut | **完全符合** | 保留 faster-whisper 与 Codex/Harness 真实算力引擎 |
| **V. 极简高效与防无用循环** | 拒绝过度工程，保持极简架构 | **完全符合** | 存储层选用 Python 内置 SQLite 模块，规避了 Node.js 原生 C++ node-gyp 交叉编译的大量复杂度和构建失败隐患 |

---

## 4. Project Structure

```text
video_cut/
├── electron.vite.config.ts                   # electron-vite 顶层编译配置
├── electron-builder.yml                      # electron-builder 双端打包配置
├── package.json                              # 整合 electron、electron-vite、electron-builder
├── src/
│   ├── main/                                 # Electron 主进程
│   │   ├── index.ts                          # 窗口生命周期、安全策略
│   │   ├── engine-manager.ts                 # Python 后台引擎拉起与健康检查
│   │   └── ipc-handlers.ts                   # 窗口控制、系统对话框
│   ├── preload/                              # 预加载脚本
│   │   ├── index.ts                          # contextBridge 暴露 window.electronAPI
│   │   └── index.d.ts                        # 类型契约声明
│   └── renderer/                             # 渲染进程 (复用当前 frontend/src)
├── backend/
│   ├── app/
│   │   ├── db/                               # SQLite 数据访问层
│   │   │   ├── session.py                    # SQLite 引擎连接与 WAL 模式
│   │   │   ├── schema.sql                    # DDL 结构定义
│   │   │   ├── repository.py                 # 素材与工程 CRUD
│   │   │   └── migrator.py                   # 旧版 JSON 数据自动迁移至 SQLite
│   │   └── ...
├── resources/
│   ├── icon.ico                              # Windows 应用图标
│   ├── icon.png                              # 通用高分图标
│   ├── icon.icns                             # macOS 应用图标
│   └── 一键解除Mac拦截.command              # 免苹果证书 Quarantine 解除脚本
└── .github/
    └── workflows/
        └── release.yml                       # GitHub Actions 跨平台双端原生编译流
```

---

## 5. Implementation Phases & Tasks

### 阶段 0: 技术调研与规范确认 (Phase 0) - [已完成]
- [x] 完成 `specs/004-electron-sqlite-cross-build/spec.md` 需求规范。
- [x] 完成 `specs/004-electron-sqlite-cross-build/research.md` 技术调研。
- [x] 完成 `specs/004-electron-sqlite-cross-build/data-model.md` SQLite 表结构与 ER 图。
- [x] 完成 `specs/004-electron-sqlite-cross-build/contracts/electron-ipc-contract.md` 通信契约。
- [x] 完成 `specs/004-electron-sqlite-cross-build/quickstart.md` 开发与打包操作指南。

### 阶段 1: SQLite 数据持久层改造 (Phase 1)
- 编写 `backend/app/db/session.py` 实现 SQLite 连接池与 WAL 模式。
- 编写 `backend/app/db/repository.py` 实现素材、剪辑工程、字幕轨道、策略工坊与设置的 SQLite CRUD。
- 编写 `backend/app/db/migrator.py`，启动时无缝将 `storage/materials_meta.json` 与 `storage/projects/*.json` 导入 SQLite。
- 改造 `backend/app/native_engine/storage.py` 与 `project_storage.py` 对接 SQLite 仓库，运行全量单测验证 100% 兼容。

### 阶段 2: Electron 主进程与渲染进程架构集成 (Phase 2)
- 在根目录配置 `package.json`，安装 `electron`, `electron-vite`, `electron-builder`。
- 配置 `electron.vite.config.ts`，配置 `src/main`, `src/preload`, `src/renderer`。
- 编写 `src/main/index.ts` 与 `src/main/engine-manager.ts`，实现应用启动自动探测与静默拉起后端算力引擎。
- 编写 `src/preload/index.ts` 暴露系统对话框、窗口操作等安全 API。
- 将前端界面接入 Electron 标题栏适配与原生对话框支持。

### 阶段 3: Windows 与 macOS 打包配置及自签名策略 (Phase 3)
- 编写 `electron-builder.yml`，配置 Windows NSIS 安装包、安装路径与快捷方式。
- 配置 macOS 的 `target: [dmg, zip]`、`identity: null` Ad-Hoc 签名。
- 编写 `resources/一键解除Mac拦截.command` 自动化免证书绕过脚本。
- 配置 `package.json` 中的构建脚本：`build:win`, `build:mac-zip`。

### 阶段 4: GitHub Actions 跨平台 CI/CD 与发包工作流 (Phase 4)
- 编写 `.github/workflows/release.yml`，定义 `windows-latest` 和 `macos-latest` 双矩阵构建。
- 接入 GitHub CLI (`gh`) 发包指引，验证打标签自动发布 Release。

---

## 决策修订记录 (2026-09-17 代码审查后)

1. **运行期数据库位置**: 维持 `storage/videocut.db`（项目根相对），**不迁移**到 `app.getPath('userData')`。打包产物以便携模式约定：主进程经 `VIDEOCUT_STORAGE_DIR` 指示引擎数据目录。原「userData」决策作废。
2. **存储真相源**: SQLite 为唯一权威存储；`materials_meta.json`、`projects/*.json` 仅作为一次性迁移输入，迁移成功后归档至 `storage/legacy/`；生产代码停止 JSON 双写（`VIDEOCUT_LEGACY_JSON=1` 可临时开启用于调试）。
3. **引擎交付形态**: 按 research.md 既定 sidecar 方案执行——PyInstaller 将 `backend/` 打为 `resources/engine/videocut-engine(.exe)`，FFmpeg 随包；动态空闲端口经 `VIDEOCUT_PORT` 环境变量传递；引擎启动失败必须显式报错，禁止静默降级开窗。
4. **词库（glossary）**: `storage/glossary.json` 为全链路唯一纠偏/热词知识源（ASR initial_prompt、embedded 替换、LLM 提示词共用）；文件缺失时纠偏链路空转并显式告警，严禁注入预置业务文案。
