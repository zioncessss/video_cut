# 需求规范 (Spec): 架构迁移至 Electron、SQLite 存储与 Windows/macOS 双端打包发布

- **功能编号**: 004
- **特性名称**: `004-electron-sqlite-cross-build`
- **状态**: Draft / Planning
- **关联宪章原则**: 
  - 原则 I：C端体验与免终端启动 (Zero-Terminal Launch)
  - 原则 II：Harness 抽象与引擎解耦
  - 原则 V：极简高效与防无用循环

---

## 1. 业务目标与用户价值

当前 `video_cut` 为独立的 Web 前端（Vite + React）与 Python 后端服务，依赖终端手动启动，且素材与工程元数据采用 JSON 扁平文件分散存储。
本特性的目标是：
1. **全桌面化封装**：通过 `electron-vite` 将应用打造成真正的桌面端原生应用，实现用户双击桌面图标即可免终端静默启动。
2. **关系型存储升级 (SQLite)**：将分散的 JSON 元数据（素材、工程、设置、字幕）整合升级为结构化、高性能的 SQLite 本地数据库，保障高并发写入与数据完整性。
3. **Windows 与 macOS 双端交叉编译与自动化发包**：
   - 开发者当前在 Windows 环境下开发，能够直接通过 `electron-builder` 本地打出 Windows 安装包 (`.exe`) 与 macOS 压缩包 (`.zip`)。
   - 针对 macOS 原生 `.dmg` 与更高规范发布，设计基于 GitHub Actions 的双矩阵原生构建流（`windows-latest` + `macos-latest`），配合 Windows 本地已有的 `gh.exe` (GitHub CLI) 实现一键发包至 GitHub Releases。
4. **macOS 免开发者账号自签名与安全规避策略**：在没有 $99/年 苹果开发者证书的前提下，提供完整的 ad-hoc 签名配置及自动化清除 Quarantine 隔离属性脚本，确保 Mac 用户下载后 100% 顺畅启动，避免触发“已损坏”或“恶意软件”拦截。

---

## 2. 功能需求与核心设计

### 2.1 Electron 架构与进程协同
- **框架选型**：`electron-vite` + `electron-builder`。
- **三层架构划分**：
  - **Main 进程 (`src/main/`)**：
    - 管理主窗口（无边框或原生标题栏、窗口大小与位置记忆、优雅淡入展示）。
    - 启动并托管内置原生后台服务（Python / Native Engine 守护子进程），实现端口动态探测与健康检查。
    - 管理本地 SQLite 数据库读写与备份。
    - 统一处理 IPC 通信（文件选择器、系统路径探测、硬件信息读取）。
  - **Preload 脚本 (`src/preload/`)**：
    - 采用安全的 `contextBridge.exposeInMainWorld` 暴露受限的安全 API (`window.electronAPI`)。
  - **Renderer 进程 (`src/renderer/`)**：
    - 复用现有的 `frontend/` React 18 + Tailwind CSS + Lucide 界面，无需重写任何视觉与交互逻辑。

### 2.2 SQLite 本地存储方案
- **数据库位置**：存储于系统的用户数据目录中（`app.getPath('userData') / 'videocut.db'`）。
- **核心数据表设计**：
  1. `materials`：素材元数据（ID、分类、文件名、物理路径、时长、宽高、帧率、创建时间）。
  2. `projects`：剪辑工程元数据（ID、标题、绑定的口播素材ID、画幅、状态、输出成片路径、创建时间、更新时间）。
  3. `subtitles`：字幕分段数据（工程ID、序号、起止时间、原文、校对文案、匹配类别、高亮关键词、绑定空镜ID）。
  4. `strategies`：剪辑策略工坊参数（工程ID、字号、位置、横幅、水印、空镜节奏）。
  5. `settings`：全局设置（活跃 Harness、模型名称、API Key、代理端点）。
- **兼容与平滑迁移**：系统首次初始化检测旧版 `storage/materials_meta.json` 与 `storage/projects/*.json`，自动导入至 SQLite，保证历史资产零丢失。

### 2.3 双端打包与 GitHub 发布工作流
- **本地 Windows 打包能力**：
  - `pnpm build:win`：生成 Windows x64 NSIS 安装程序（安装向导、桌面快捷方式、卸载清理）。
  - `pnpm build:mac-local`：在 Windows 下通过 `electron-builder --mac zip` 输出适用于 macOS 的 `.zip` 应用包。
- **基于 GitHub Actions 的企业级双端发包流水线**：
  - 在 `.github/workflows/release.yml` 中定义矩阵构建：
    - Runner 1: `windows-latest` 编译生成 `VideoCut-Setup-<version>.exe`。
    - Runner 2: `macos-latest` 编译生成支持 Apple Silicon (arm64) 与 Intel (x64) 的原生 `VideoCut-<version>.dmg` 与 `VideoCut-<version>-mac.zip`。
  - 触发机制：本地使用 `git tag v1.0.0 && git push origin v1.0.0` 或运行 `gh workflow run release.yml`，GitHub 云端自动编译并把全套跨平台安装包挂载在 GitHub Release 供用户直接下载。

### 2.4 macOS 免证书快速自签名与安全绕过策略
- **问题根源**：macOS Gatekeeper 对未签名或未公证（Notarization）的外部下载应用会自动附加 `com.apple.quarantine` 扩展属性，拦截并报“应用已损坏，应移入废纸篓”。
- **自签名配置**：在 `electron-builder.yml` 中显式设置 `mac.identity = null`，关闭 `hardenedRuntime`，采用自包含 Ad-Hoc 代码签名。
- **免证书一键解锁交付方案**：
  - 在打包输出中附带一个纯原生的 `.command` 双击运行脚本：
    ```bash
    #!/bin/bash
    echo "正在为您解除 macOS 系统的安全性拦截..."
    sudo xattr -r -d com.apple.quarantine "/Applications/VideoCut.app" 2>/dev/null || xattr -r -d com.apple.quarantine "$0/../VideoCut.app"
    echo "拦截已成功解除！现在您可以直接打开 VideoCut 了。"
    ```
  - DMG 安装背景图中标注清晰的操作指示（“若提示损坏，请右键打开或运行解除脚本”），彻底免去 $99/年 的苹果开发者证书开销。

---

## 3. 验收标准 (Acceptance Criteria)

1. **零终端启动**：主进程双击启动后，自动拉起图形界面并隐式激活后台引擎，无任何黑框命令行弹出。
2. **SQLite 正常读写**：
   - 素材上传与删除、剪辑工程保存、字幕热更新全部写入 `videocut.db`。
   - 重启应用后所有数据瞬间恢复。
3. **打包产物**：
   - 在 Windows 开发机上运行打包命令能成功产出 Windows 可执行文件。
   - 提供配置完整的 GitHub Actions 跨平台发布配置文件，具备 Windows + macOS DMG 完整构建能力。
4. **发包说明与自签名工具链**：
   - 提供详细的 GitHub CLI (`gh`) 登录与发包指南。
   - 提供 macOS 用户免认证风险解除策略与交付物。
