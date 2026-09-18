import os
import shutil
import subprocess
import psutil
from typing import Optional
from app.models.entities import HardwareMetrics

_detected_gpu_accelerator: Optional[str] = None
_gpu_checked = False

def detect_gpu_accelerator() -> Optional[str]:
    global _detected_gpu_accelerator, _gpu_checked
    if _gpu_checked:
        return _detected_gpu_accelerator
    
    _gpu_checked = True
    if not shutil.which("ffmpeg"):
        return None

    try:
        res = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        out = res.stdout.lower()
        if "h264_nvenc" in out:
            _detected_gpu_accelerator = "nvenc"
        elif "h264_videotoolbox" in out:
            _detected_gpu_accelerator = "videotoolbox"
        elif "h264_qsv" in out:
            _detected_gpu_accelerator = "qsv"
        else:
            _detected_gpu_accelerator = None
    except Exception:
        _detected_gpu_accelerator = None

    return _detected_gpu_accelerator

def get_hardware_metrics() -> HardwareMetrics:
    cores = os.cpu_count() or 4
    cpu_pct = psutil.cpu_percent(interval=0.1)
    vm = psutil.virtual_memory()
    mem_total_gb = round(vm.total / (1024 ** 3), 1)
    mem_avail_gb = round(vm.available / (1024 ** 3), 1)
    gpu_acc = detect_gpu_accelerator()

    # 并发公式：基于可用物理内存与CPU核心数自适应计算
    # 单槽位内存预算 1.5GB（whisper base float32 ≈1GB + NVENC 渲染 ≈0.5GB），
    # 旧值 2.0GB 在 16GB 机器上过于保守（可用 5GB 时只给 2 并发）
    calc_concurrency = max(1, min(cores // 2, int(mem_avail_gb // 1.5)))

    return HardwareMetrics(
        cpu_cores=cores,
        cpu_percent=cpu_pct,
        memory_total_gb=mem_total_gb,
        memory_available_gb=mem_avail_gb,
        gpu_accelerator_detected=gpu_acc,
        recommended_concurrency=calc_concurrency
    )
