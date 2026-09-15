import sys
import os
import threading
import time
import webbrowser
from pathlib import Path

# 将 backend 加入搜索路径
ROOT_DIR = Path(__file__).resolve().parent
backend_dir = ROOT_DIR / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def start_backend():
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=18888, log_level="warning")

def main():
    # 1. 后台线程静默启动 FastAPI 核心引擎
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    time.sleep(1.2)  # 等待服务端口绑定

    target_url = "http://127.0.0.1:18888/app/"
    dev_url = "http://127.0.0.1:5173"  # 前端本地开发服务器备用
    
    # 优先检测本地打包或开发页面
    url_to_open = target_url

    # 2. 尝试使用 PyWebView 唤起原生桌面窗体（免黑框终端）
    try:
        import webview
        window = webview.create_window(
            title="VideoCut 驾校短视频网感剪辑工作台",
            url=url_to_open,
            width=1360,
            height=860,
            min_size=(1080, 720),
            background_color="#F8FAFC"
        )
        webview.start()
    except Exception as e:
        print(f"WebView launch fallback: {e}")
        # 若系统缺少原生 WebView 运行时，自动优雅唤起默认浏览器窗口
        webbrowser.open(url_to_open)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
