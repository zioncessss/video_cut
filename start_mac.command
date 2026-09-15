#!/bin/bash
# VideoCut macOS 一键启动脚本
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python launcher.py
else
    python3 launcher.py
fi
