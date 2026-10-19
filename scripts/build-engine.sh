#!/usr/bin/env bash
# Build the compute-engine sidecar on macOS (arm64 or x86_64)
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$DIR/.." && pwd )"
ARCH=$(uname -m)
for arg in "$@"; do
    case $arg in
        --arch=x64|--arch=x86_64|x64|x86_64)
            ARCH="x86_64"
            ;;
        --arch=arm64|arm64)
            ARCH="arm64"
            ;;
    esac
done

echo "========================================================"
echo "  VideoCut macOS 算力引擎构建工具 (目标架构: $ARCH)"
echo "========================================================"

PYTHON="python3"
if [ -f "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
fi

if [ "$ARCH" = "x86_64" ] && [ "$(uname -m)" = "arm64" ]; then
    echo "提示：在 Apple Silicon 主机上构建 x86_64 架构，启用 Rosetta 2 转译..."
    PYTHON="arch -x86_64 $PYTHON"
fi

echo "[1/4] 检查 PyInstaller 环境..."
$PYTHON -m pip install -q pyinstaller || true

echo "[2/4] 构建 macOS Mach-O videocut-engine 算力引擎 ($ARCH)..."
WORK_PATH="$ROOT/build_engine"
DIST_PATH="$WORK_PATH/dist"
SCHEMA_SRC="$ROOT/backend/app/db/schema.sql"

$PYTHON -m PyInstaller \
  --noconfirm --clean \
  --name videocut-engine \
  --target-arch "$ARCH" \
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

# 检查已存在 ffmpeg 架构，若与目标架构不符则清理重拉
if [ -f "$FFMPEG_DEST" ]; then
    if [ "$ARCH" = "x86_64" ] && ! file "$FFMPEG_DEST" | grep -qE "x86_64|universal"; then
        echo "  清理非 x86_64 架构的旧 ffmpeg..."
        rm -f "$FFMPEG_DEST"
    elif [ "$ARCH" = "arm64" ] && ! file "$FFMPEG_DEST" | grep -qE "arm64|universal"; then
        echo "  清理非 arm64 架构的旧 ffmpeg..."
        rm -f "$FFMPEG_DEST"
    fi
fi

if [ -f "$FFPROBE_DEST" ]; then
    if [ "$ARCH" = "x86_64" ] && ! file "$FFPROBE_DEST" | grep -qE "x86_64|universal"; then
        echo "  清理非 x86_64 架构的旧 ffprobe..."
        rm -f "$FFPROBE_DEST"
    elif [ "$ARCH" = "arm64" ] && ! file "$FFPROBE_DEST" | grep -qE "arm64|universal"; then
        echo "  清理非 arm64 架构的旧 ffprobe..."
        rm -f "$FFPROBE_DEST"
    fi
fi

if [ ! -f "$FFMPEG_DEST" ]; then
    echo "  正在拉取 static ffmpeg for $CURL_ARCH..."
    curl -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-$CURL_ARCH" -o "$FFMPEG_DEST"
fi

if [ ! -f "$FFPROBE_DEST" ]; then
    echo "  正在拉取 static ffprobe for $CURL_ARCH..."
    curl -fSL "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-$CURL_ARCH" -o "$FFPROBE_DEST"
fi

chmod +x "$ROOT/resources/engine/bin/"* 2>/dev/null || true

mkdir -p "$ROOT/resources/default_storage"
[ -f "$ROOT/storage/glossary.json" ] && cp "$ROOT/storage/glossary.json" "$ROOT/resources/default_storage/" || true
[ -f "$ROOT/storage/banned_words.json" ] && cp "$ROOT/storage/banned_words.json" "$ROOT/resources/default_storage/" || true

echo ""
echo "--- 架构一致性校验 ---"
file "$ROOT/resources/engine/videocut-engine/videocut-engine"
file "$FFMPEG_DEST"
file "$FFPROBE_DEST"

if [ "$ARCH" = "x86_64" ]; then
    file "$ROOT/resources/engine/videocut-engine/videocut-engine" | grep -qE "x86_64|universal" || { echo "❌ 致命错误: videocut-engine 不是 x86_64 架构!"; exit 1; }
    file "$FFMPEG_DEST" | grep -qE "x86_64|universal" || { echo "❌ 致命错误: ffmpeg 不是 x86_64 架构!"; exit 1; }
else
    file "$ROOT/resources/engine/videocut-engine/videocut-engine" | grep -qE "arm64|universal" || { echo "❌ 致命错误: videocut-engine 不是 arm64 架构!"; exit 1; }
    file "$FFMPEG_DEST" | grep -qE "arm64|universal" || { echo "❌ 致命错误: ffmpeg 不是 arm64 架构!"; exit 1; }
fi

echo "========================================================"
echo "  ✅ macOS videocut-engine ($ARCH) 算力引擎与依赖组件构建成功！"
echo "========================================================"
