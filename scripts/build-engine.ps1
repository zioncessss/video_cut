# Build the compute-engine sidecar: PyInstaller packs backend into resources/engine/videocut-engine(.exe)
# Usage (repo root): powershell -ExecutionPolicy Bypass -File scripts/build-engine.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { $VenvPython = "python" }
$exeName = "videocut-engine.exe"

Write-Host "[1/4] Ensuring PyInstaller is available..."
$VenvBin = Split-Path -Parent $VenvPython
$PyInstExe = Join-Path $VenvBin "pyinstaller.exe"
if (-not (Test-Path $PyInstExe)) { & uv pip install pyinstaller --python $VenvPython }
if (-not (Test-Path $PyInstExe)) { throw "PyInstaller unavailable (tried: uv pip install pyinstaller)" }

Write-Host "[2/4] Packing backend with PyInstaller (collect core dependencies & API routes)..."
$WorkPath = Join-Path $Root "build_engine"
$DistPath = Join-Path $WorkPath "dist"
$SchemaSrc = Join-Path $Root "backend\app\db\schema.sql"
& $VenvPython -m PyInstaller `
  --noconfirm --clean `
  --name videocut-engine `
  --paths (Join-Path $Root "backend") `
  --collect-all certifi `
  --collect-all cv2 `
  --collect-all PIL `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan.on `
  --hidden-import PIL `
  --hidden-import cv2 `
  --hidden-import numpy `
  --hidden-import certifi `
  --hidden-import multipart `
  --hidden-import app.api.materials `
  --hidden-import app.api.editor `
  --hidden-import app.api.batch `
  --hidden-import app.api.instruction `
  --hidden-import app.api.system `
  --hidden-import app.api.settings `
  --hidden-import app.api.chat `
  --hidden-import app.harness_bridge.factory `
  --hidden-import app.harness_bridge.api_engine `
  --hidden-import app.harness_bridge.codex `
  --hidden-import app.harness_bridge.zcode `
  --hidden-import app.harness_bridge.embedded `
  --add-data "$SchemaSrc`;app/db" `
  (Join-Path $Root "backend\engine_main.py") `
  --distpath $DistPath --workpath (Join-Path $WorkPath "work") --specpath $WorkPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

Write-Host "[3/4] Placing artifact into resources/engine/videocut-engine/..."
$EngineDir = Join-Path $Root "resources\engine"
New-Item -ItemType Directory -Force -Path $EngineDir | Out-Null
$AppDir = Join-Path $DistPath "videocut-engine"
$TargetDir = Join-Path $EngineDir "videocut-engine"
if (-not (Test-Path (Join-Path $AppDir $exeName))) { throw "Build output not found: $AppDir" }
if (Test-Path $TargetDir) { Remove-Item $TargetDir -Recurse -Force }
Copy-Item $AppDir $TargetDir -Recurse -Force

Write-Host "[4/4] Ensuring static FFmpeg & Seeding default storage..."
$BinDir = Join-Path $EngineDir "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$ffmpegDest = Join-Path $BinDir "ffmpeg.exe"
if (-not (Test-Path $ffmpegDest)) {
    $ffmpegCandidates = @(
        (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue).Source,
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe",
        "C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        "$env:USERPROFILE\scoop\shims\ffmpeg.exe",
        "C:\ffmpeg\bin\ffmpeg.exe"
    )
    foreach ($cand in $ffmpegCandidates) {
        if ($cand -and (Test-Path $cand)) {
            Copy-Item $cand $ffmpegDest -Force
            Write-Host "  Copied ffmpeg.exe from $cand"
            break
        }
    }
}
if (-not (Test-Path $ffmpegDest)) {
    Write-Host "  Downloading static standalone ffmpeg.exe from GitHub..."
    curl.exe -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-win32-x64" -o $ffmpegDest
}

$ffprobeDest = Join-Path $BinDir "ffprobe.exe"
if (-not (Test-Path $ffprobeDest)) {
    $ffprobeCandidates = @(
        (Get-Command ffprobe.exe -ErrorAction SilentlyContinue).Source,
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffprobe.exe",
        "C:\ProgramData\chocolatey\bin\ffprobe.exe",
        "$env:USERPROFILE\scoop\shims\ffprobe.exe",
        "C:\ffmpeg\bin\ffprobe.exe"
    )
    foreach ($cand in $ffprobeCandidates) {
        if ($cand -and (Test-Path $cand)) {
            Copy-Item $cand $ffprobeDest -Force
            Write-Host "  Copied ffprobe.exe from $cand"
            break
        }
    }
}
if (-not (Test-Path $ffprobeDest)) {
    Write-Host "  Downloading static standalone ffprobe.exe from GitHub..."
    curl.exe -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-win32-x64" -o $ffprobeDest
}

$DefStorageDir = Join-Path $Root "resources\default_storage"
New-Item -ItemType Directory -Force -Path $DefStorageDir | Out-Null
if (Test-Path (Join-Path $Root "storage\glossary.json")) {
    Copy-Item (Join-Path $Root "storage\glossary.json") (Join-Path $DefStorageDir "glossary.json") -Force
}
if (Test-Path (Join-Path $Root "storage\banned_words.json")) {
    Copy-Item (Join-Path $Root "storage\banned_words.json") (Join-Path $DefStorageDir "banned_words.json") -Force
}

Write-Host "Done: $TargetDir\$exeName"
