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

Write-Host "[2/4] Packing backend with PyInstaller (collect faster-whisper/ctranslate2)..."
$WorkPath = Join-Path $Root "build_engine"
$DistPath = Join-Path $WorkPath "dist"
$SchemaSrc = Join-Path $Root "backend\app\db\schema.sql"
& $VenvPython -m PyInstaller `
  --noconfirm --clean `
  --name videocut-engine `
  --paths (Join-Path $Root "backend") `
  --collect-all faster_whisper `
  --collect-all ctranslate2 `
  --collect-all av `
  --hidden-import uvicorn.logging `
  --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto `
  --hidden-import uvicorn.protocols.websockets.auto `
  --hidden-import uvicorn.lifespan.on `
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

Write-Host "[4/4] Copying FFmpeg & Seeding default storage..."
$BinDir = Join-Path $EngineDir "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$ffmpegSrc = (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue).Source
if ($ffmpegSrc) { Copy-Item $ffmpegSrc (Join-Path $BinDir "ffmpeg.exe") -Force; Write-Host "  ffmpeg.exe bundled" }
else { Write-Host "  [WARN] ffmpeg.exe not found on PATH; put it into resources/engine/bin manually" }
$ffprobeSrc = (Get-Command ffprobe.exe -ErrorAction SilentlyContinue).Source
if ($ffprobeSrc) { Copy-Item $ffprobeSrc (Join-Path $BinDir "ffprobe.exe") -Force }

$DefStorageDir = Join-Path $Root "resources\default_storage"
New-Item -ItemType Directory -Force -Path $DefStorageDir | Out-Null
if (Test-Path (Join-Path $Root "storage\glossary.json")) {
    Copy-Item (Join-Path $Root "storage\glossary.json") (Join-Path $DefStorageDir "glossary.json") -Force
}
if (Test-Path (Join-Path $Root "storage\banned_words.json")) {
    Copy-Item (Join-Path $Root "storage\banned_words.json") (Join-Path $DefStorageDir "banned_words.json") -Force
}

Write-Host "Done: $TargetDir\$exeName"
