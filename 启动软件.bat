@echo off
chcp 65001 >nul
title VideoCut 驾校短视频网感剪辑工作台
color 0B

echo ================================================================
echo   VideoCut 驾校短视频网感剪辑工作台
echo   正在启动本地引擎并自动打开浏览器...
echo ================================================================

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py
) else (
    python launcher.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [提示] 服务已停止或发生异常。
    pause
)
