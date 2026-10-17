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

## 🍏 macOS 用户安装与权限避坑指南 (Intel & Apple Silicon)

### 1. 芯片架构精准选择（非常重要！）
在 GitHub Releases 下载页面，我们提供了针对不同 Mac 芯片原生编译的独立安装包：
- **Intel 芯片 Mac**（MacBook Pro / Air / iMac / Mac mini 2020 年前机型）：
  👉 **请下载 `VideoCut-*-x64-mac.dmg`**（或 `*-x64-mac.zip`）。
  *(注意：Intel 芯片无法执行 arm64 程序，请勿下载 arm64 安装包)*
- **Apple Silicon 芯片 Mac**（M1 / M2 / M3 / M4 系列机型）：
  👉 **请下载 `VideoCut-*-arm64-mac.dmg`**（或 `*-arm64-mac.zip`）。
  *(原生满血运行，无需经 Rosetta 2 转译)*

### 2. 解压与安装避坑说明
> [!IMPORTANT]
> **强烈推荐优先下载 `.dmg` 格式安装包**！
> - **为什么优先用 DMG？**
>   macOS 原生 DMG 镜像天然完整保留所有底层可执行组件（主进程、Python 算力引擎、FFmpeg / FFprobe）的 `0755` 运行权限。
> - **若下载了 `.zip` 压缩包解压**：
>   某些解压软件或在 Windows 下中转解压时会抹除 Unix 可执行权限位，导致双击报“无权限打开”。
>   为此，VideoCut 主进程内部已集成**运行时权限自愈机制 (Runtime Self-Healing)**，在检测到权限缺失时将主动修复 `chmod +x`。

> [!WARNING]
> **必须拖拽安装至 `/Applications` (应用程序) 目录**：
> 请勿直接在“下载 (Downloads)”文件夹中双击运行。macOS 会对未安装的 App 实施 **App Translocation (安全易位执行)**，将其映射至临时只读虚拟沙盒，可能导致媒体暂存与 SQLite 数据库出现只读报错。

### 3. macOS 安全拦截（Gatekeeper）一键解除
由于本应用为开源社区免费发布、未向苹果公司缴纳 $99/年 商业开发者证书，首次在 macOS 14 (Sonoma) / macOS 15 (Sequoia) 打开时，苹果 Gatekeeper 会提示：
*“已损坏，无法打开。你应该将它移到废纸篓”* 或 *“无法打开，因为 Apple 无法检查其是否包含恶意软件”*。

只需执行以下任意一种方式即可一劳永逸解除：
- **方式一（一键脚本，小白推荐）**：
  双击运行随包附带的 **`一键解除Mac拦截.command`**（或 `scripts/fix-macos-gatekeeper.command`），按提示输入开机密码回车即可自动完成：
  1. 深度清除 Gatekeeper Quarantine 隔离属性；
  2. 递归校验并赋予底层二进制（FFmpeg / Python 引擎）执行权限；
  3. 注入本地 Ad-Hoc 签名凭据。
- **方式二（终端单行命令，极客推荐）**：
  打开 Mac 终端 (Terminal)，复制并执行以下命令回车：
  ```bash
  sudo xattr -cr /Applications/VideoCut.app && sudo codesign --force --deep --sign - /Applications/VideoCut.app
  ```
- **方式三（系统偏好设置）**：
  前往「系统设置 (System Settings)」->「隐私与安全性 (Privacy & Security)」，滑动到最下方点击「仍要打开 (Open Anyway)」即可。