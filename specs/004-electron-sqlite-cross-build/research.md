# 技术调研与架构决策 (Research & Technical Decisions)

- **功能编号**: 004
- **特性名称**: `004-electron-sqlite-cross-build`
- **调研对象**: Electron + electron-vite + electron-builder, SQLite 存储方案, Windows/macOS 交叉编译, GitHub Actions 自动化发包, macOS 免证书自签名

---

## 1. Electron + electron-vite 项目结构与演化方案

### 1.1 为什么选择 electron-vite？
- **传统 Electron + Vite 的痛点**：通常需要分别维护主进程构建、预加载脚本构建和渲染进程构建，热重载（HMR）配置繁琐，多进程 TypeScript 编译容易出现路径别名断裂。
- **electron-vite 的优势**：
  - 原生一体化多进程构建：一个 `electron.vite.config.ts` 集中管理 `main`, `preload`, `renderer`。
  - 开箱即用支持 Main/Preload 源代码修改毫秒级热重载，无需每次重启整个 Electron 进程。
  - 完美无缝继承现有 `frontend/` 中的 React 18, Tailwind CSS, Lucide 图标和 Vite 插件。

### 1.2 目录拓扑结构设计
```text
video_cut/
├── electron.vite.config.ts        # electron-vite 顶层编译配置
├── electron-builder.yml           # electron-builder 双端打包与发布配置
├── package.json                   # 包含 electron, electron-vite, electron-builder
├── src/
│   ├── main/                      # Electron 主进程
│   │   ├── index.ts               # 窗口创建、生命周期、子进程拉起
│   │   └── backend-runner.ts      # Python 后台引擎守护与健康检查
│   ├── preload/                   # 预加载脚本
│   │   ├── index.ts               # contextBridge 安全暴露
│   │   └── index.d.ts             # 类型声明
│   └── renderer/                  # 渲染进程（即现在的 React 前端）
│       ├── index.html
│       ├── src/                   # 对应当前的 frontend/src
│       └── ...
├── backend/                       # 原生 Python 算力引擎（ASR + FFmpeg + Harness）
│   ├── app/
│   │   ├── db/                    # 新增：SQLite 数据库连接与 ORM/DAO
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   └── migrations.py
│   │   └── ...
└── .github/
    └── workflows/
        └── release.yml            # GitHub Actions 跨平台原生打包发布流水线
```

---

## 2. 后端算力引擎与 Electron 的协同运行模式

### 2.1 运行模式调研
- **开发态（Development）**：
  - Electron 主进程启动时，探测 `http://127.0.0.1:18888/api/v1/settings`：
    - 若本地已在运行后端，直接复用连接。
    - 若未运行，主进程自动通过 `child_process.spawn` 静默拉起本地 Python 虚拟环境中的后端服务。
- **生产打包态（Production Package）**：
  - 采用 **Sidecar 独立算力进程打包**（业界如 Cursor、LM Studio、Whisper Desktop 的通用标准）：
  - 通过 `extraResources` 将打包好的 Python 引擎及 FFmpeg 二进制放置在应用的资源目录（`resources/engine/`）。
  - 主进程启动后拉起 `resources/engine/videocut-engine.exe`（Windows）或 `videocut-engine`（macOS），监听动态端口并通过环境变量通信。
  - 应用关闭时，主进程监听 `window-all-closed` 与 `before-quit`，发送优雅退出信号彻底杀掉子进程，坚决不残留僵尸进程。

---

## 3. SQLite 本地存储架构设计

### 3.1 方案选型：Node `better-sqlite3` vs Python 内置 `sqlite3`
| 维度 | Node.js `better-sqlite3` | Python 内置 `sqlite3` + WAL |
| :--- | :--- | :--- |
| **C++ 跨平台编译摩擦** | 极高（需通过 `node-gyp` 和 `electron-rebuild` 编译各平台的动态链接库，Windows 交叉编译 Mac 会直接报错） | **零摩擦（Python 标准库内置，各平台 100% 具备）** |
| **与现有算力层的集成** | 需通过大量 IPC 桥接在 Node 和 Python 之间传大量元数据 | **天然与 ASR、FFmpeg、LLM 纠错无缝结合** |
| **并发与性能** | 单线程同步阻塞/异步线程池 | 开启 `PRAGMA journal_mode=WAL;` 后支持极高并发读写 |
| **结论** | 不建议用于跨平台交叉打包 | **推荐采用：Python 内置 SQLite 模块构建持久层，无任何 C++ 原生编译痛点** |

### 3.2 数据库 Schema 与迁移策略
数据库文件存放路径：用户本地应用数据目录中的 `videocut.db`。
- **表 1: `materials`** (素材元数据)
  - `id` (TEXT PRIMARY KEY), `category` (TEXT), `filename` (TEXT), `filepath` (TEXT), `duration` (REAL), `width` (INTEGER), `height` (INTEGER), `fps` (REAL), `created_at` (REAL)
- **表 2: `projects`** (剪辑工程)
  - `id` (TEXT PRIMARY KEY), `title` (TEXT), `talking_head_id` (TEXT, 关联 materials.id), `aspect_ratio` (TEXT), `status` (TEXT), `output_video_path` (TEXT), `raw_asr_json` (TEXT), `created_at` (REAL), `updated_at` (REAL)
- **表 3: `subtitles`** (字幕与空镜分配)
  - `id` (TEXT PRIMARY KEY), `project_id` (TEXT, FOREIGN KEY), `sort_index` (INTEGER), `start_time` (REAL), `end_time` (REAL), `raw_text` (TEXT), `corrected_text` (TEXT), `matched_category` (TEXT), `matched_keywords` (TEXT), `broll_material_id` (TEXT), `is_manual_edited` (INTEGER)
- **表 4: `strategies`** (剪辑策略工坊参数)
  - `project_id` (TEXT PRIMARY KEY), `subtitle_theme` (TEXT), `font_size` (TEXT), `show_subtitles` (INTEGER), `subtitle_position_y` (INTEGER), `subtitle_position_x` (INTEGER), `enable_highlight` (INTEGER), `highlight_color` (TEXT), `enable_top_banner` (INTEGER), `banner_main_title` (TEXT), `banner_sub_title` (TEXT), `banner_style` (TEXT), `enable_watermark` (INTEGER), `watermark_text` (TEXT), `watermark_position` (TEXT), `watermark_opacity` (REAL), `broll_pacing` (TEXT)
- **表 5: `settings`** (全局与引擎配置)
  - `key` (TEXT PRIMARY KEY), `value` (TEXT), `updated_at` (REAL)

---

## 4. Windows 与 macOS 双端打包与发包策略

### 4.1 在 Windows 宿主机上本地交叉构建的能力边界
- **Windows 构建**：`electron-builder --win nsis` 可直接产出完美安装包 `.exe`。
- **macOS 构建限制**：
  - Windows 原生无法直接调用 macOS 专属内核模块打出 `.dmg`（会因缺少 hfsplus / dmg-license 报错或需要繁琐的 Wine 环境）。
  - 但 Windows 能够**完美打出 macOS 的 `.zip` 安装包（包含完整的 `.app` 目录结构）**！
  - 因此：本地 Windows 提供 `pnpm build:win`（产出 `.exe`）和 `pnpm build:mac-zip`（产出 `.zip`）。

### 4.2 GitHub Actions 企业级原生双端构建方案 (标准推荐)
- **优势**：
  - GitHub 提供免费的 macOS 托管运行器（`macos-latest`），可以直接在纯正 macOS 环境下构建经过验证的 `.dmg` 和 `.zip`（支持 Intel x64 与 Apple Silicon M1/M2/M3/M4 arm64）。
  - Windows 托管运行器（`windows-latest`）构建原生 NSIS `.exe`。
- **流程设计**：
  ```mermaid
  flowchart TD
      Local[开发者本地打标签: git tag v1.0.0] --> Push[git push origin v1.0.0]
      Push --> Actions[GitHub Actions release.yml]
      subgraph Matrix [并发矩阵构建]
        WinRunner[windows-latest] --> BuildExe[electron-builder --win\n产出 VideoCut-Setup-1.0.0.exe]
        MacRunner[macos-latest] --> BuildDmg[electron-builder --mac\n产出 VideoCut-1.0.0-arm64.dmg\n和 VideoCut-1.0.0-x64.dmg]
      end
      Actions --> Matrix
      BuildExe --> GHRelease[自动上传至 GitHub Releases]
      BuildDmg --> GHRelease
      GHRelease --> EndUser[终端用户直接下载安装]
  ```

### 4.3 GitHub 发包工具链与插件
- 本地机器已安装官方 **GitHub CLI** (`gh.exe`，位于 `C:\Program Files\GitHub CLI\gh.exe`)。
- 开发者只需在终端执行一次：
  ```powershell
  gh auth login
  ```
  按照交互式提示使用浏览器扫码或授权登录 GitHub 账号即可。
- 后续发布时，可直接通过一条命令全自动化创建 Release 并挂载本地编译包：
  ```powershell
  gh release create v1.0.0 ./release/*.exe ./release/*.zip --title "VideoCut v1.0.0" --notes "首次双端桌面发布"
  ```

---

## 5. macOS 免苹果开发者证书的快速自签名与安全绕过策略

### 5.1 苹果 Gatekeeper 机制剖析
- 未购买 $99 苹果开发者证书并经过 Apple 公证（Notarization）的软件，在 macOS 上下载后会被系统附加扩展隔离属性：`com.apple.quarantine`。
- 双击运行时，macOS 会弹窗警告：
  > “VideoCut”已损坏，无法打开。你应该将它移到废纸篓。
  或者：
  > 打不开“VideoCut”，因为 Apple 无法检查其是否包含恶意软件。

### 5.2 解决方案组合拳
1. **Ad-Hoc 快速自签名**：
   - 在 `electron-builder.yml` 中配置：
     ```yaml
     mac:
       target:
         - target: dmg
           arch:
             - x64
             - arm64
         - target: zip
           arch:
             - x64
             - arm64
       identity: null
       hardenedRuntime: false
       gatekeeperAssess: false
     ```
   - 在 macOS 构建时，执行 `codesign --force --deep --sign - /path/to/VideoCut.app`，赋予合法的本地自签名凭据。
2. **免证书一键解除隔离拦截脚本（交付神器）**：
   - 打包时在根目录附带一个无特权限制的可执行脚本：`一键解除Mac拦截.command`：
     ```bash
     #!/bin/bash
     APP_PATH="/Applications/VideoCut.app"
     if [ ! -d "$APP_PATH" ]; then
         APP_PATH="$(dirname "$0")/VideoCut.app"
     fi
     echo "=================================================="
     echo "  正在为您解除 macOS 系统对 VideoCut 的安全性拦截  "
     echo "=================================================="
     xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null || true
     echo "✅ 拦截已成功解除！"
     echo "您现在可以直接双击打开 VideoCut 软件了。"
     ```
   - 用户下载解压后，如果遇到系统拦截，只需右键运行该脚本，或者在终端执行一次 `xattr -cr /Applications/VideoCut.app`，即可永久畅玩，完全无需苹果开发者账号！
