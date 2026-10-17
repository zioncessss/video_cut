#!/usr/bin/env bash
# Build the compute-engine sidecar on macOS (arm64 or x86_64)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$DIR/.." && pwd )"
ARCH=$(uname -m)

echo "========================================================"
echo "  VideoCut macOS 算力引擎构建工具 (架构: $ARCH)"
echo "========================================================"

PYTHON="python3"
if [ -f "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
fi

echo "[1/4] 检查 PyInstaller 环境..."
$PYTHON -m pip install -q pyinstaller || true

echo "[2/4] 构建 macOS Mach-O videocut-engine 算力引擎..."
WORK_PATH="$ROOT/build_engine"
DIST_PATH="$WORK_PATH/dist"
SCHEMA_SRC="$ROOT/backend/app/db/schema.sql"

$PYTHON -m PyInstaller \
  --noconfirm --clean \
  --name videocut-engine \
  --paths "$ROOT/backend" \
  --collect-all certifi \
  --collect-all cv2 \
  --collect-all PIL \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --hidden-import PIL \
  --hidden-import cv2 \
  --hidden-import numpy \
  --hidden-import certifi \
  --hidden-import multipart \
  --hidden-import app.api.materials \
  --hidden-import app.api.editor \
  --hidden-import app.api.batch \
  --hidden-import app.api.instruction \
  --hidden-import app.api.system \
  --hidden-import app.api.settings \
  --hidden-import app.api.chat \
  --hidden-import app.harness_bridge.factory \
  --hidden-import app.harness_bridge.api_engine \
  --hidden-import app.harness_bridge.codex \
  --hidden-import app.harness_bridge.zcode \
  --hidden-import app.harness_bridge.embedded \
  --add-data "$SCHEMA_SRC:app/db" \
  "$ROOT/backend/engine_main.py" \
  --distpath "$DIST_PATH" --workpath "$WORK_PATH/work" --specpath "$WORK_PATH"

echo "[3/4] 部署引擎产物至 resources/engine/videocut-engine..."
mkdir -p "$ROOT/resources/engine"
rm -rf "$ROOT/resources/engine/videocut-engine"
cp -r "$DIST_PATH/videocut-engine" "$ROOT/resources/engine/"
chmod -R +x "$ROOT/resources/engine/videocut-engine"

echo "[4/4] 就绪对应芯片架构 ($ARCH) 的静态独立 FFmpeg & 默认词库..."
mkdir -p "$ROOT/resources/engine/bin"
FFMPEG_DEST="$ROOT/resources/engine/bin/ffmpeg"
FFPROBE_DEST="$ROOT/resources/engine/bin/ffprobe"

CURL_ARCH="arm64"
if [ "$ARCH" = "x86_64" ]; then
    CURL_ARCH="x64"
fi

if [ ! -f "$FFMPEG_DEST" ]; then
    if command -v ffmpeg >/dev/null 2>&1; then
        cp "$(which ffmpeg)" "$FFMPEG_DEST"
    else
        echo "  正在拉取 static ffmpeg for $CURL_ARCH..."
        curl -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-$CURL_ARCH" -o "$FFMPEG_DEST"
    fi
fi

if [ ! -f "$FFPROBE_DEST" ]; then
    if command -v ffprobe >/dev/null 2>&1; then
        cp "$(which ffprobe)" "$FFPROBE_DEST"
    else
        echo "  正在拉取 static ffprobe for $CURL_ARCH..."
        curl -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-$CURL_ARCH" -o "$FFPROBE_DEST"
    fi
fi

chmod +x "$ROOT/resources/engine/bin/"* 2>/dev/null || true

mkdir -p "$ROOT/resources/default_storage"
[ -f "$ROOT/storage/glossary.json" ] && cp "$ROOT/storage/glossary.json" "$ROOT/resources/default_storage/" || true
[ -f "$ROOT/storage/banned_words.json" ] && cp "$ROOT/storage/banned_words.json" "$ROOT/resources/default_storage/" || true

echo "========================================================"
echo "  ✅ macOS videocut-engine 算力引擎构建成功！"
echo "========================================================"
