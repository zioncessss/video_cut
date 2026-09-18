# VideoCut - 驾校短视频极速剪辑与智能混剪桌面客户端

VideoCut 是一款专为驾校场景打造的口播短视频剪辑与批量混剪桌面工具。采用 **Electron + React + Tailwind + SQLite (WAL 模式) + Python 算力引擎 (faster-whisper + FFmpeg + LLM)** 现代化跨平台架构。

---

## 🌟 核心特性

- 🖥️ **跨平台原生桌面端**：基于 `electron-vite` 与 `electron-builder` 构建，无终端黑框，后台静默拉起与守护算力引擎。
- 🗄️ **高性能 SQLite 关系型存储**：采用 SQLite WAL 模式，素材元数据、剪辑工程、字幕切片、样式策略原子化存取与历史无缝自动迁移。
- 🎙️ **MiniMax 云端极速 ASR 与字级时间戳**：对接 MiniMax `asr-1.0` 接口，1~2 分钟音频秒级转写；基于字级声学时间戳、标点感知与 8~18 字弹性单行，100% 消除中文短语腰斩（“千万不 / 要报”）与走马灯微短碎片（<1s），支持离线 Faster-Whisper 无缝降级。
- 🎬 **稀疏 Cue Sheet 与双层 60%~70% 智能分镜编排**：MiniMax 大模型仅输出高相关稀疏分镜点位（`broll_cues`，Token < 300，秒级响应）；独创“语义强相关精准锚定 + 自由主体随机铺底”双层编排引擎，硬性保障 60%~70% 黄金空镜覆盖率，严格守护开场 1.8s 真人、手势报价句与结尾 CTA 三大禁切红线。
- ⚙️ **设置中心统一凭据与双通道连通性诊断**：集中管理 MiniMax Key 与模型配置，支持一键探测 LLM（首字延迟 TTFT）与 ASR 接口双通道健康度，凭据前端绝不明文暴露。
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