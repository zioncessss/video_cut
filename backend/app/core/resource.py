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

    # 视频合成处理资源调度算法 (Video Composition Concurrency Scheduler):
    # 彻底解绑本地 ASR 限制（ASR 已全面上云/直连 API，无需为 Whisper 预留显存/内存）。
    # 纯按视频合成压制（FFmpeg filter_complex + 解码 + 编码 + Lanczos 缩放 + ASS渲染）的资源开销进行自主调度：
    if gpu_acc:
        # GPU 硬件加速模式 (NVENC / QSV / VideoToolbox):
        # 单任务内存开销极低 (~300MB-500MB)，瓶颈主要受显卡硬件编码 Session 上限（消费级显卡多为 3~5 路）与可用内存约束
        calc_concurrency = max(1, min(cores // 2, int(mem_avail_gb // 0.8), 4))
    else:
        # CPU 软解软压模式 (libx264):
        # 单任务需分配 3~4 个线程与 ~1.0GB 内存保证压制吞吐率，避免 CPU 100% 抢占导致操作系统卡死
        calc_concurrency = max(1, min(cores // 3, int(mem_avail_gb // 1.2), 3))

    return HardwareMetrics(
        cpu_cores=cores,
        cpu_percent=cpu_pct,
        memory_total_gb=mem_total_gb,
        memory_available_gb=mem_avail_gb,
        gpu_accelerator_detected=gpu_acc,
        recommended_concurrency=calc_concurrency
    )
