<#
.SYNOPSIS
  VideoCut GitHub 一键发布流水线触发与打包脚本
.DESCRIPTION
  帮助开发者在 Windows 本地使用 gh.exe 检查登录状态、创建 Release 标签并触发 GitHub Actions 跨平台编译。
#>

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       VideoCut 跨平台自动化发包工具 (GitHub CLI)          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. 检测 gh.exe 是否安装并可用
$ghPath = Get-Command gh.exe -ErrorAction SilentlyContinue
if (-not $ghPath) {
    Write-Host "❌ 未检测到 gh.exe，请确保 GitHub CLI 已安装并添加到 PATH。" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 检测到 GitHub CLI: $($ghPath.Source)" -ForegroundColor Green

# 2. 检查登录状态
Write-Host "`n正在检查 GitHub 登录凭据..." -ForegroundColor Yellow
$authStatus = gh auth status 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ 您当前尚未登录 GitHub CLI。" -ForegroundColor Yellow
    Write-Host "👉 正在唤起登录向导，请选择 'GitHub.com' -> 'HTTPS' -> 'Yes' (网页登录):" -ForegroundColor Cyan
    gh auth login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 登录取消或失败，发包终止。" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ GitHub CLI 已成功登录。" -ForegroundColor Green
}

# 3. 输入发布版本号
$defaultVersion = "v1.0.0"
$version = Read-Host "`n请输入要发布的版本号 (默认: $defaultVersion)"
if ([string]::IsNullOrWhiteSpace($version)) {
    $version = $defaultVersion
}

if (-not ($version.StartsWith("v"))) {
    $version = "v$version"
}

Write-Host "`n准备发布版本: $version" -ForegroundColor Cyan
$releaseNote = Read-Host "请输入本次 Release 的更新说明 (例如: 支持 Electron 桌面端与 SQLite 架构)"
if ([string]::IsNullOrWhiteSpace($releaseNote)) {
    $releaseNote = "VideoCut $version 发布 - 支持 Electron 桌面端、SQLite 存储与 Windows/macOS 双端打包"
}

# 4. 创建 Git Tag 并推送到远程
Write-Host "`n正在打标签 $version 并推送到远程仓库..." -ForegroundColor Yellow
git tag -a $version -m "$releaseNote"
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ 本地已存在该标签或存在冲突，尝试覆盖打标..." -ForegroundColor Yellow
    git tag -d $version 2>$null
    git tag -a $version -m "$releaseNote"
}

git push origin $version --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 推送 Tag 失败，请检查是否已关联远程仓库 (git remote -v) 及推送权限。" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Tag $version 已成功推送到 GitHub！" -ForegroundColor Green
Write-Host "🚀 GitHub Actions 跨平台构建矩阵已自动启动！" -ForegroundColor Cyan
Write-Host "稍后可在 GitHub 仓库的 Actions 与 Releases 页面下载 Windows (.exe) 与 macOS (.dmg/.zip) 安装包！" -ForegroundColor Green