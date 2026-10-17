param(
    [string]$Version = "",
    [string]$ReleaseNote = ""
)

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       VideoCut 跨平台自动化发包工具 (GitHub CLI)          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. 检查当前 Git 分支状态
$currentBranch = git branch --show-current
Write-Host "📍 当前工作分支: $currentBranch" -ForegroundColor Cyan

# 2. 检查登录状态
Write-Host "`n正在检查 GitHub 凭据..." -ForegroundColor Yellow
$ghPath = Get-Command gh.exe -ErrorAction SilentlyContinue
if ($ghPath) {
    $authStatus = gh auth status 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ GitHub CLI 已成功登录。" -ForegroundColor Green
    } else {
        Write-Host "⚠️ GitHub CLI 尚未登录，将尝试通过 Git 凭据推送。" -ForegroundColor Yellow
    }
}

# 3. 确定发布版本号
$defaultVersion = "v1.0.0"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Read-Host "`n请输入要发布的版本号 (默认: $defaultVersion)"
}
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = $defaultVersion
}

if (-not ($Version.StartsWith("v"))) {
    $Version = "v$Version"
}

Write-Host "`n准备发布版本: $Version" -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($ReleaseNote)) {
    $ReleaseNote = Read-Host "请输入本次 Release 的更新说明 (例如: 支持 Electron 桌面端与 SQLite 架构)"
}
if ([string]::IsNullOrWhiteSpace($ReleaseNote)) {
    $ReleaseNote = "VideoCut $Version 发布 - 支持 Windows x64 与 macOS (Intel x64 + Apple Silicon arm64) 跨平台原生打包"
}

# 4. 推送当前代码分支至远程
Write-Host "`n正在推送代码分支 $currentBranch 到 GitHub 远程仓库..." -ForegroundColor Yellow
git push origin $currentBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ 推送分支可能存在冲突或网络异常，尝试推送 Tag..." -ForegroundColor Yellow
}

# 5. 创建 Git Tag 并推送到远程
Write-Host "`n正在打标签 $Version 并推送到远程仓库..." -ForegroundColor Yellow
git tag -a $Version -m "$ReleaseNote"
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ 本地已存在该标签或存在冲突，尝试覆盖打标..." -ForegroundColor Yellow
    git tag -d $Version 2>$null
    git tag -a $Version -m "$ReleaseNote"
}

git push origin $Version --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 推送 Tag 失败，请检查是否已关联远程仓库 (git remote -v) 及推送权限。" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Tag $version 已成功推送到 GitHub！" -ForegroundColor Green
Write-Host "🚀 GitHub Actions 跨平台构建矩阵已自动启动！" -ForegroundColor Cyan
Write-Host "稍后可在 GitHub 仓库的 Actions 与 Releases 页面下载 Windows (.exe) 与 macOS (.dmg/.zip) 安装包！" -ForegroundColor Green