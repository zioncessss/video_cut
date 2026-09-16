# 快速开始与操作指南 (Quickstart & Operations Guide)

- **功能编号**: 004
- **特性名称**: `004-electron-sqlite-cross-build`

---

## 1. 开发环境运行

### 1.1 安装前端与 Electron 依赖
在项目根目录下执行：
```powershell
pnpm install
```

### 1.2 启动桌面开发态（一体化热更新）
```powershell
pnpm dev
```
- 主进程将自动启动。
- 若后端未启动，主进程将自动拉起 Python 算力引擎。
- 渲染进程通过 Vite 启动，窗口自动打开，支持代码修改毫秒级热更新。

---

## 2. 本地 Windows 宿主机打包编译

### 2.1 构建 Windows 原生安装包 (`.exe`)
在 Windows 开发机终端执行：
```powershell
pnpm build:win
```
- **产物位置**：`dist/VideoCut-Setup-1.0.0.exe`
- **特性**：包含完整 NSIS 安装向导、自动创建桌面快捷方式与开始菜单项、自动附带卸载工具。

### 2.2 在 Windows 宿主机上打出 macOS 压缩包 (`.zip`)
在 Windows 终端执行：
```powershell
pnpm build:mac-zip
```
- **产物位置**：`dist/VideoCut-1.0.0-mac.zip`
- **特性**：解压后直接为完整的 `VideoCut.app` 应用程序包，无需 Wine 即可完成编译。

---

## 3. GitHub 跨平台自动化发包 (推荐流水线)

借助 GitHub Actions 云端原生的 macOS 与 Windows 运行器，能够自动化编译出最标准的双端成片（含 macOS 原生 `.dmg` 安装盘）。

### 3.1 一次性登录与绑定 GitHub CLI
您的电脑已安装 `gh.exe`，请在终端执行一次：
```powershell
gh auth login
```
选择 `GitHub.com` -> `HTTPS` -> `Yes` (用浏览器登录)，完成授权即可。

### 3.2 关联 GitHub 远程仓库 (如果尚未关联)
```powershell
git remote add origin https://github.com/<您的用户名>/video_cut.git
git branch -M main
git push -u origin main
```

### 3.3 一键发布新版本 (CI/CD 自动构建双端)
发布新版本只需打一个版本标签并推送：
```powershell
git tag v1.0.0
git push origin v1.0.0
```
GitHub Actions 会自动启动双矩阵编译：
1. `windows-latest` 产出 `VideoCut-Setup-1.0.0.exe`
2. `macos-latest` 产出 `VideoCut-1.0.0.dmg` 与 `VideoCut-1.0.0-mac.zip`
3. 自动在 GitHub 创建 Release `v1.0.0` 并挂载这三个安装包供所有人下载！

---

## 4. macOS 免开发者账号自签名与安全规避操作

如果您或您的用户在 macOS 系统上下载了安装包，双击遇到“应用已损坏，应移入废纸篓”或“无法验证开发者”提示：

### 极速解除方案（二选一）：
1. **方式一：双击附带脚本（零代码小白推荐）**
   - 双击安装包附带的 `一键解除Mac拦截.command` 脚本文件。
   - 终端会自动弹出并打印 `✅ 拦截已成功解除！`，随后即可直接打开 VideoCut。
2. **方式二：终端单行指令**
   - 打开 Mac 终端，复制粘贴并执行：
     ```bash
     sudo xattr -r -d com.apple.quarantine /Applications/VideoCut.app
     ```
   - 永久解除隔离属性，彻底省去每年 $99 的苹果税！
