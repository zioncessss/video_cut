import sys
import os
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
backend_dir = ROOT_DIR / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

log_file = ROOT_DIR / "launcher.log"
TARGET_URL = "http://127.0.0.1:18888/"
HEALTH_URL = "http://127.0.0.1:18888/api/health"

def log(msg: str):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def is_server_ready(timeout=0.8) -> bool:
    try:
        # 固定本机健康检查地址，字面量内联，杜绝任何动态 URL 来源
        with urllib.request.urlopen("http://127.0.0.1:18888/api/health", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

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

    # 1. 检测服务是否已在运行中（防止重复启动报错）
    if is_server_ready():
        log("Backend is already running. Opening browser directly...")
        webbrowser.open(TARGET_URL)
        return

    # 2. 启动后台服务守护线程
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()

    # 3. 等待服务就绪（最多等待 6 秒）
    log("Waiting for backend service to become ready...")
    ready = False
    for _ in range(30):
        if is_server_ready(0.2):
            ready = True
            break
        time.sleep(0.2)

    if ready:
        log("Backend service is ready! Automatically opening browser...")
    else:
        log("Backend service wait timed out, attempting to open browser anyway...")

    # 4. 自动打开系统默认浏览器（Chrome / Edge / 默认浏览器）
    webbrowser.open(TARGET_URL)
    log(f"Browser opened with target URL: {TARGET_URL}")

    # 5. 保持主进程常驻，持续提供后端服务
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("Launcher stopped by user.")

if __name__ == "__main__":
    main()
