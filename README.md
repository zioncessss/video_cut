# VideoCut - 驾校短视频极速剪辑与智能混剪桌面客户端

VideoCut 是一款专为驾校场景打造的口播短视频剪辑与批量混剪桌面工具。采用 **Electron + React + Tailwind + SQLite (WAL 模式) + Python 算力引擎 (faster-whisper + FFmpeg + LLM)** 现代化跨平台架构。

---

## 🌟 核心特性

- 🖥️ **跨平台原生桌面端**：基于 `electron-vite` 与 `electron-builder` 构建，无终端黑框，后台静默拉起与守护算力引擎。
- 🗄️ **高性能 SQLite 关系型存储**：采用 SQLite WAL 模式，素材元数据、剪辑工程、字幕切片、样式策略原子化存取与历史无缝自动迁移。
- 🎙️ **真实 ASR 与大模型语义纠错**：支持口播字幕高精度识别，自动提取核心词高亮，专有词库智能纠正。
- 📦 **Windows 与 macOS 双端打包**：
  - Windows 开发机本地一键产出 `.exe` 安装包与 `.zip` Mac 应用包。
  - 接入 GitHub Actions 矩阵流水线，自动构建 macOS 原生 `.dmg` 与发布 Releases。
- 🍏 **macOS 免开发者账号自签名方案**：附带一键脚本，绕过苹果 Gatekeeper Quarantine 拦截，无需购买 $99/年 开发者证书。

---

## 🚀 快速开始

### 1. 安装与运行
```powershell
# 1. 安装前端与 Electron 依赖
pnpm install

# 2. 启动桌面应用开发环境 (一体化热更新)
pnpm dev
```

### 2. 本地构建打包 (Windows 开发机)
```powershell
# 构建 Windows 安装程序 (.exe)
pnpm build:win

# 构建 macOS 应用程序压缩包 (.zip)
pnpm build:mac-zip
```
打包输出目录：`dist/`

---

## 🤖 自动化发包 (GitHub Actions & GitHub CLI)

如果您已安装 GitHub CLI (`gh.exe`)，可直接运行快捷脚本触发跨平台双端打包流水线：
```powershell
.\scripts\publish-release.ps1
```
推送版本标签后，GitHub Actions 会在云端 Windows 与 macOS 机器上并行构建，自动生成 Release 供用户下载。

---

## 🍏 macOS 用户拦截快速解除

在 Mac 上双击打开若提示“应用已损坏，应移入废纸篓”或“无法验证开发者”：
1. **方式一（推荐）**：双击运行安装包内的 `resources/一键解除Mac拦截.command` 脚本。
2. **方式二（终端）**：在 Mac 终端中执行：
   ```bash
   sudo xattr -r -d com.apple.quarantine /Applications/VideoCut.app
   ```