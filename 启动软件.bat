@echo off
chcp 65001 >nul
title VideoCut 驾校短视频网感剪辑工作台
color 0B

echo ================================================================
echo   VideoCut 驾校短视频网感剪辑工作台
echo   正在启动本地混合引擎与桌面界面...
echo ================================================================

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launcher.py
) else (
    python launcher.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [错误] 启动过程中遇到异常，请检查上述输出。
    pause
)
