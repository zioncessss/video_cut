"""VideoCut 算力引擎打包入口（PyInstaller sidecar）。

打包产物 resources/engine/videocut-engine(.exe) 的启动入口：
端口与数据目录由 Electron 主进程经环境变量注入（VIDEOCUT_PORT / VIDEOCUT_STORAGE_DIR），
实现动态端口通信与便携化数据目录（见 specs/004 plan.md 决策修订记录）。
"""
import os

# 静态导入核心图像/计算依赖与 API 路由，确保 PyInstaller 依赖追踪期无一遗漏
try:
    import PIL
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    import cv2
    import numpy
    from app.api import materials, editor, batch, instruction, system
except Exception as e:
    # 模块缺失直接打印告警
    print(f"[engine_main] Pre-import verification error: {e}")


def main() -> None:
    host = os.getenv("VIDEOCUT_HOST", "127.0.0.1")
    port = int(os.getenv("VIDEOCUT_PORT", "18888"))
    storage_dir = os.getenv("VIDEOCUT_STORAGE_DIR", "")
    if storage_dir:
        os.environ["VIDEOCUT_STORAGE_DIR"] = storage_dir

    import uvicorn

    # 直接传应用对象（打包环境无法保证字符串导入路径可用）
    from app.main import app

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
