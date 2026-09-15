import sys
import os
import threading
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
backend_dir = ROOT_DIR / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

log_file = ROOT_DIR / "launcher.log"

def log(msg: str):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def start_backend():
    try:
        log("Starting FastAPI backend on 127.0.0.1:18888...")
        import uvicorn
        from app.main import app
        uvicorn.run(app, host="127.0.0.1", port=18888, log_level="warning")
    except Exception as e:
        log(f"Backend fatal error: {e}")

def main():
    log("=== VideoCut Launcher Starting ===")
    
    # 1. 启动后端守护线程
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    time.sleep(1.2)

    target_url = "http://127.0.0.1:18888/"
    log(f"Target URL: {target_url}")

    # 2. 尝试唤起桌面窗口 (优先 pywebview，失败或无环境时自动打开系统默认浏览器)
    gui_started = False
    try:
        log("Attempting to launch native desktop window with pywebview...")
        import webview
        window = webview.create_window(
            title="VideoCut 驾校短视频网感剪辑工作台",
            url=target_url,
            width=1360,
            height=860,
            min_size=(1080, 720),
            background_color="#F8FAFC"
        )
        log("Calling webview.start()...")
        webview.start()
        gui_started = True
        log("webview.start() closed normally.")
    except Exception as e:
        log(f"pywebview GUI launch notice/exception: {e}")

    if not gui_started:
        log("Opening in default web browser as desktop fallback...")
        webbrowser.open(target_url)
        # 保持进程常驻为浏览器服务
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Launcher exiting.")

if __name__ == "__main__":
    main()
