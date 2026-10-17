import subprocess
import shutil
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import io
import base64
from PIL import Image, ImageDraw, ImageFont

@dataclass
class FilterPresetParams:
    name: str
    description: str
    smartblur_lr: float = 1.0
    smartblur_ls: float = 0.25
    smartblur_lt: float = -3.5
    eq_contrast: float = 1.04
    eq_brightness: float = 0.02
    eq_saturation: float = 1.06
    eq_gamma: float = 1.03
    eq_gamma_r: float = 1.0
    eq_gamma_b: float = 1.0
    cas_strength: float = 0.30
    # 行业级影视与人像色彩分级微调参数 (直接复用成熟色彩平衡方案)
    colorbalance_rs: float = 0.0
    colorbalance_gs: float = 0.0
    colorbalance_bs: float = 0.0
    colorbalance_rm: float = 0.0
    colorbalance_gm: float = 0.0
    colorbalance_bm: float = 0.0
    colorbalance_rh: float = 0.0
    colorbalance_gh: float = 0.0
    colorbalance_bh: float = 0.0
    vignette_angle: Optional[str] = None

PORTRAIT_PRESETS: Dict[str, Optional[FilterPresetParams]] = {
    "cold_white": FilterPresetParams(
        name="冷白暖亮",
        description="面部冷白透亮去黄，背景环境温暖提亮，驱散室内暗沉发青，呈现阳光通透美感",
        smartblur_lr=1.2,
        smartblur_ls=0.35,
        smartblur_lt=-4.0,
        eq_contrast=1.05,
        eq_brightness=0.055,
        eq_saturation=1.07,
        eq_gamma=1.06,
        eq_gamma_r=1.01,
        eq_gamma_b=1.03,
        colorbalance_rs=0.03,
        colorbalance_gs=0.01,
        colorbalance_bs=-0.02,
        colorbalance_rm=0.02,
        colorbalance_gm=0.01,
        colorbalance_bm=-0.02,
        colorbalance_rh=0.04,
        colorbalance_gh=0.01,
        colorbalance_bh=-0.04,
        cas_strength=0.30
    ),
    "clean_natural": FilterPresetParams(
        name="自然通透",
        description="面部暗沉驱散，皮肤质感自然白皙，发丝与眼神光清晰，适合日常手机口播",
        smartblur_lr=1.0,
        smartblur_ls=0.25,
        smartblur_lt=-3.5,
        eq_contrast=1.04,
        eq_brightness=0.02,
        eq_saturation=1.06,
        eq_gamma=1.03,
        cas_strength=0.30
    ),
    "teal_orange": FilterPresetParams(
        name="电影青橙",
        description="国际大片黄金色调，阴影泛冷青蓝，高光肤色温暖立体，高级院线电影质感",
        smartblur_lr=0.8,
        smartblur_ls=0.20,
        smartblur_lt=-3.0,
        eq_contrast=1.08,
        eq_brightness=0.01,
        eq_saturation=1.12,
        eq_gamma=1.02,
        colorbalance_bs=0.06,
        colorbalance_gs=0.01,
        colorbalance_bm=-0.03,
        colorbalance_rm=0.04,
        colorbalance_rh=0.06,
        colorbalance_gh=0.02,
        colorbalance_bh=-0.05,
        cas_strength=0.35
    ),
    "crisp_hd": FilterPresetParams(
        name="质感超清",
        description="边缘轮廓极其立体硬朗，抗二次压缩能力最强，适合商单讲解与高质感需求",
        smartblur_lr=0.8,
        smartblur_ls=0.15,
        smartblur_lt=-3.0,
        eq_contrast=1.06,
        eq_brightness=0.01,
        eq_saturation=1.04,
        eq_gamma=1.01,
        cas_strength=0.40
    ),
    "warm_radiant": FilterPresetParams(
        name="元气暖肤",
        description="微升色温，面颊红润通透，改善苍白疲惫或冷光灯泛青泛灰",
        smartblur_lr=1.2,
        smartblur_ls=0.30,
        smartblur_lt=-4.0,
        eq_contrast=1.03,
        eq_brightness=0.03,
        eq_saturation=1.08,
        eq_gamma=1.04,
        eq_gamma_r=1.02,
        eq_gamma_b=0.98,
        cas_strength=0.25
    ),
    "vintage_film": FilterPresetParams(
        name="复古胶片",
        description="模拟经典胶片温润色调，微黄暖调，带有边缘柔和暗角，富有叙事与怀旧质感",
        smartblur_lr=1.0,
        smartblur_ls=0.22,
        smartblur_lt=-3.5,
        eq_contrast=1.03,
        eq_brightness=0.01,
        eq_saturation=1.05,
        eq_gamma=1.02,
        colorbalance_rs=0.02,
        colorbalance_gs=0.02,
        colorbalance_rm=0.02,
        colorbalance_bm=-0.03,
        colorbalance_bh=-0.04,
        vignette_angle="PI/5",
        cas_strength=0.25
    ),
    "original": None  # Bypass: 保持素材原始色彩
}

def build_portrait_filter_chain(preset: str = "clean_natural", strength: float = 1.0, has_cas: bool = True) -> str:
    """
    组装针对真人出镜口播的高清画质调优滤镜子串：
    1. 若为 original 或 strength <= 0.01，完全旁路返回空字符串。
    2. 参数按 strength 线性插值，平滑过渡。
    3. 组装流水线：smartblur(保边磨皮) -> colorbalance(冷暖影视分级) -> eq(通透提亮) -> vignette(胶片暗角) -> cas(自适应超清锐化)。
    """
    if preset not in PORTRAIT_PRESETS or preset == "original":
        return ""
    params = PORTRAIT_PRESETS.get(preset)
    if not params:
        return ""
    str_val = max(0.0, min(1.0, float(strength)))
    if str_val <= 0.01:
        return ""

    eff_ls = round(params.smartblur_ls * str_val, 2)
    eff_contrast = round(1.0 + (params.eq_contrast - 1.0) * str_val, 3)
    eff_brightness = round(0.0 + (params.eq_brightness - 0.0) * str_val, 3)
    eff_saturation = round(1.0 + (params.eq_saturation - 1.0) * str_val, 3)
    eff_gamma = round(1.0 + (params.eq_gamma - 1.0) * str_val, 3)
    eff_gamma_r = round(1.0 + (params.eq_gamma_r - 1.0) * str_val, 3)
    eff_gamma_b = round(1.0 + (params.eq_gamma_b - 1.0) * str_val, 3)
    eff_cas = round(params.cas_strength * str_val, 2)

    parts = []
    # 1. 智能保边平滑磨皮
    if eff_ls > 0.01:
        parts.append(f"smartblur=lr={params.smartblur_lr:.2f}:ls={eff_ls:.2f}:lt={params.smartblur_lt:.2f}")

    # 2. 影视级色彩平衡 (三向色温插值)
    cb_args = []
    if abs(params.colorbalance_rs) > 0.001: cb_args.append(f"rs={params.colorbalance_rs * str_val:.3f}")
    if abs(params.colorbalance_gs) > 0.001: cb_args.append(f"gs={params.colorbalance_gs * str_val:.3f}")
    if abs(params.colorbalance_bs) > 0.001: cb_args.append(f"bs={params.colorbalance_bs * str_val:.3f}")
    if abs(params.colorbalance_rm) > 0.001: cb_args.append(f"rm={params.colorbalance_rm * str_val:.3f}")
    if abs(params.colorbalance_gm) > 0.001: cb_args.append(f"gm={params.colorbalance_gm * str_val:.3f}")
    if abs(params.colorbalance_bm) > 0.001: cb_args.append(f"bm={params.colorbalance_bm * str_val:.3f}")
    if abs(params.colorbalance_rh) > 0.001: cb_args.append(f"rh={params.colorbalance_rh * str_val:.3f}")
    if abs(params.colorbalance_gh) > 0.001: cb_args.append(f"gh={params.colorbalance_gh * str_val:.3f}")
    if abs(params.colorbalance_bh) > 0.001: cb_args.append(f"bh={params.colorbalance_bh * str_val:.3f}")
    if cb_args:
        parts.append(f"colorbalance={':'.join(cb_args)}")

    # 3. 对比度、亮度、饱和度与伽马微调
    eq_args = [
        f"contrast={eff_contrast:.3f}",
        f"brightness={eff_brightness:.3f}",
        f"saturation={eff_saturation:.3f}",
        f"gamma={eff_gamma:.3f}"
    ]
    if abs(eff_gamma_r - 1.0) >= 0.005:
        eq_args.append(f"gamma_r={eff_gamma_r:.3f}")
    if abs(eff_gamma_b - 1.0) >= 0.005:
        eq_args.append(f"gamma_b={eff_gamma_b:.3f}")
    parts.append(f"eq={':'.join(eq_args)}")

    # 4. 可选复古暗角
    if params.vignette_angle and str_val > 0.1:
        parts.append(f"vignette=angle={params.vignette_angle}")

    # 5. CAS / Unsharp 边缘细节与瞳孔超清微锐化
    if eff_cas > 0.01:
        if has_cas:
            parts.append(f"cas={eff_cas:.2f}")
        else:
            parts.append(f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={eff_cas:.2f}:chroma_amount=0.0")

    return ",".join(parts)

def _get_flame_icon(size: int) -> Optional[Image.Image]:
    """利用 Windows 原生 Segoe UI Emoji 字体生成高保真真彩 🔥 图标"""
    emoji_font_path = Path("C:/Windows/Fonts/seguiemj.ttf")
    if emoji_font_path.exists():
        try:
            render_size = max(32, size * 2)
            f = ImageFont.truetype(str(emoji_font_path), render_size)
            img = Image.new("RGBA", (int(render_size * 1.4), int(render_size * 1.4)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.text((0, 0), "🔥", font=f, embedded_color=True)
            bbox = img.getbbox()
            if bbox:
                cropped = img.crop(bbox)
                w = max(1, int(cropped.width * size / cropped.height))
                return cropped.resize((w, size), Image.Resampling.LANCZOS)
        except Exception:
            pass
    return None

def _build_atempo_chain(speed: float) -> str:
    """
    FFmpeg atempo 滤镜要求单级参数在 [0.5, 2.0] 区间内。
    若倍速超出此区间（如 2.5x 或 0.4x），自动多级串联（如 atempo=2.0,atempo=1.25）。
    """
    spd = max(0.25, min(4.0, float(speed)))
    factors = []
    curr = spd
    while curr > 2.0:
        factors.append("2.0")
        curr /= 2.0
    while curr < 0.5:
        factors.append("0.5")
        curr /= 0.5
    factors.append(str(round(curr, 4)))
    return ",".join(f"atempo={f}" for f in factors)

class FFmpegFilterComposer:
    def __init__(self):
        self.has_ffmpeg = bool(shutil.which("ffmpeg"))
        self._has_cas: Optional[bool] = None
        self._cached_encode_args: Optional[List[str]] = None
        self._hdr_cache: Dict[str, bool] = {}

    def get_video_encode_args(self) -> List[str]:
        """
        探测并返回最优的视频编码参数。
        优先启用硬件加速 (AMD AMF / NVIDIA NVENC / Intel QSV)，
        若不可用则无缝回退至多线程 CPU 编码 (libx264 -preset veryfast -crf 18 -threads 0)。
        """
        if self._cached_encode_args is not None:
            return list(self._cached_encode_args)

        if not self.has_ffmpeg:
            self._cached_encode_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "0"]
            return list(self._cached_encode_args)

        # 0. 尝试 Apple VideoToolbox (macOS 专属原生硬件加速引擎，极速低功耗)
        if sys.platform == "darwin":
            try:
                test_cmd = [
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.04",
                    "-c:v", "h264_videotoolbox", "-q:v", "65",
                    "-f", "null", "-"
                ]
                res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                if res.returncode == 0:
                    self._cached_encode_args = [
                        "-c:v", "h264_videotoolbox",
                        "-q:v", "65",
                    ]
                    return list(self._cached_encode_args)
            except Exception:
                pass

        # 1. 尝试 AMD AMF (如 AMD Radeon 显卡)
        try:
            test_cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.04",
                "-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20",
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if res.returncode == 0:
                self._cached_encode_args = [
                    "-c:v", "h264_amf",
                    "-quality", "balanced",
                    "-rc", "cqp",
                    "-qp_i", "18",
                    "-qp_p", "20",
                ]
                return list(self._cached_encode_args)
        except Exception:
            pass

        # 2. 尝试 NVIDIA NVENC (开启空间/时间自适应量化AQ，彻底杜绝面部和暗部色块)
        try:
            test_cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.04",
                "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-spatial-aq", "1", "-temporal-aq", "1",
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if res.returncode == 0:
                self._cached_encode_args = [
                    "-c:v", "h264_nvenc",
                    "-preset", "p5",
                    "-cq", "19",
                    "-spatial-aq", "1",
                    "-temporal-aq", "1",
                ]
                return list(self._cached_encode_args)
        except Exception:
            pass

        # 3. 尝试 Intel QSV
        try:
            test_cmd = [
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.04",
                "-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "18",
                "-f", "null", "-"
            ]
            res = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if res.returncode == 0:
                self._cached_encode_args = [
                    "-c:v", "h264_qsv",
                    "-preset", "medium",
                    "-global_quality", "18",
                ]
                return list(self._cached_encode_args)
        except Exception:
            pass

        # 4. CPU 回退 (极速多线程)
        self._cached_encode_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-threads", "0",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        ]
        return list(self._cached_encode_args)

    def _run_ffmpeg_with_cpu_fallback(self, cmd: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """
        执行 FFmpeg 压制。
        若使用了 GPU 硬件加速 (AMF/NVENC/QSV) 且执行失败，自动无缝降级为多线程 CPU (libx264) 极速重试，
        确保在任何显卡驱动异常或特定滤镜不兼容时 100% 不崩溃、成片不损坏。
        """
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if res.returncode == 0:
            return res

        hw_codecs = ("h264_amf", "h264_nvenc", "h264_qsv", "h264_videotoolbox")
        used_hw = any(codec in cmd for codec in hw_codecs)
        if used_hw:
            err_str = res.stderr.decode("utf-8", errors="replace")
            print(f"[FFmpegFilterComposer] GPU 硬件编码执行异常 (exit {res.returncode}): {err_str[-200:]}，自动触发 CPU (libx264 veryfast) 兜底重试...")
            self._cached_encode_args = [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "18",
                "-threads", "0",
                "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
            ]
            cpu_cmd = []
            skip = 0
            for idx, arg in enumerate(cmd):
                if skip > 0:
                    skip -= 1
                    continue
                if arg == "-c:v" and idx + 1 < len(cmd) and cmd[idx + 1] in hw_codecs:
                    cpu_cmd.extend(self._cached_encode_args)
                    skip = 1
                    for ahead_i in range(idx + 2, min(idx + 12, len(cmd))):
                        if cmd[ahead_i] in ("-quality", "-rc", "-qp_i", "-qp_p", "-preset", "-cq", "-global_quality", "-q:v", "-b:v"):
                            skip += 2
                    continue
                cpu_cmd.append(arg)
            res_retry = subprocess.run(cpu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if res_retry.returncode == 0:
                print("[FFmpegFilterComposer] CPU 极速多线程重试成功，已顺利完成全片压制！")
            return res_retry

        return res

    def check_has_cas(self) -> bool:
        if self._has_cas is None:
            if not self.has_ffmpeg:
                self._has_cas = False
            else:
                try:
                    res = subprocess.run(["ffmpeg", "-h", "filter=cas"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
                    self._has_cas = (res.returncode == 0)
                except Exception:
                    self._has_cas = False
        return self._has_cas

    def build_scale_filter(self, aspect_ratio: str = "9:16") -> str:
        """根据目标比例构建归一化缩放与无裁剪填充滤镜（采用高吞吐 Bicubic 重采样兼顾高画质与极致压制速度）"""
        if aspect_ratio == "9:16":
            return "scale=1080:1920:force_original_aspect_ratio=decrease:flags=bicubic+accurate_rnd,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        return "scale=1920:1080:force_original_aspect_ratio=decrease:flags=bicubic+accurate_rnd,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"

    def is_hdr_video(self, video_path: Path) -> bool:
        """
        精准探测视频是否为 HDR / 宽色域格式（iPhone HLG arib-std-b67, HDR10 smpte2084, 杜比视界, BT.2020 色域）
        具备文件 mtime 级持久化内存缓存，杜绝重复调用外部 ffprobe 子进程
        """
        if not self.has_ffmpeg or not video_path.exists():
            return False

        cache_key = None
        try:
            resolved_p = str(video_path.resolve())
            mtime = video_path.stat().st_mtime
            cache_key = f"{resolved_p}_{mtime}"
            if cache_key in self._hdr_cache:
                return self._hdr_cache[cache_key]
        except Exception:
            cache_key = None

        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=color_space,color_primaries,color_transfer,pix_fmt",
                "-of", "default=noprint_wrappers=1",
                str(video_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            stdout = res.stdout if isinstance(res.stdout, str) else (res.stdout.decode("utf-8", errors="ignore") if res.stdout else "")
            out = stdout.lower()
            is_hdr = any(t in out for t in ("arib-std-b67", "smpte2084", "bt2020", "dovi"))
            if cache_key:
                self._hdr_cache[cache_key] = is_hdr
            return is_hdr
        except Exception:
            return False

    def build_color_normalize_filter(
        self,
        is_hdr: bool,
        target_w: int,
        target_h: int,
        filter_preset: str = "original",
        filter_strength: float = 1.0
    ) -> str:
        """
        全链路色彩与画质归一化滤镜：
        1. 若输入为 iPhone HDR / 杜比视界 / HLG / BT.2020：
           利用 zscale + tonemap(hable) 进行广播级 HDR 到 SDR BT.709 色调映射，
           彻底消除过曝、惨白、红脸偏色问题，精准保留原素材动态范围与肤色质感。
        2. 针对真人出镜口播进行三阶微调（微平滑净肤 -> 通透提亮暖肤色 -> CAS 对比度自适应微锐化）。
           【黑边防灰铁律】：滤镜必须在 scale 之后、pad 补黑边之前执行，严禁将纯黑边变灰！
        3. 若输入为常规 SDR：强制统一像素格式为 yuv420p 并打标 bt709，杜绝多素材拼接时色彩空间冲突。
        4. 配合高吞吐 Bicubic 缩放与居中黑边补齐，释放 GPU 编码器最大吞吐。
        """
        scale = f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=bicubic+accurate_rnd"
        pad = f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
        portrait_chain = build_portrait_filter_chain(filter_preset, filter_strength, has_cas=self.check_has_cas())

        if portrait_chain:
            scale_and_filter = f"{scale},{portrait_chain},{pad}"
        else:
            scale_and_filter = f"{scale},{pad}"

        color_meta = (
            "format=yuv420p,"
            "sidedata=mode=delete:type=AMBIENT_VIEWING_ENVIRONMENT,"
            "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
        )

        if is_hdr:
            return (
                f"zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,"
                f"zscale=p=bt709:t=bt709:m=bt709:r=limited,"
                f"{color_meta},"
                f"{scale_and_filter}"
            )
        else:
            return (
                f"{scale_and_filter},"
                f"{color_meta}"
            )

    def generate_overlay_canvas(
        self,
        target_w: int,
        target_h: int,
        strategy: Dict[str, Any],
        output_overlay_path: Path
    ) -> Optional[Path]:
        """
        利用 Pillow 生成与前端 DOM 100% 像素级对齐的无损透明图层：
        1. 包含圆角胶囊半透明磨砂底框、🔥 真彩 Emoji、粗体主标题、金色副标语的挂顶 Banner。
        2. 包含自适应圆角微底框的右上角 / 自由定位品牌水印角标。
        """
        has_banner = bool(strategy.get("enable_top_banner") and str(strategy.get("banner_main_title") or "").strip())
        wm_text = str(strategy.get("watermark_text") or "").strip()
        has_watermark = bool(strategy.get("enable_watermark") and wm_text and wm_text != "@顺达驾校官方教学")

        if not has_banner and not has_watermark:
            return None

        canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        title_font_path = "C:/Windows/Fonts/msyhbd.ttc"
        sub_font_path = "C:/Windows/Fonts/msyh.ttc"

        def _get_font(path: str, size: int):
            alt_font = "C:/Windows/Fonts/simhei.ttf"
            try:
                if Path(path).exists():
                    return ImageFont.truetype(path, size)
                elif Path(alt_font).exists():
                    return ImageFont.truetype(alt_font, size)
            except Exception:
                pass
            return ImageFont.load_default()

        # 1. 绘制顶部挂顶横幅 (圆角胶囊底框 + 🔥 Emoji + 白金双色文字)
        if has_banner:
            title = str(strategy.get("banner_main_title", "")).strip()
            sub_title = str(strategy.get("banner_sub_title") or "").strip()

            banner_font_size = strategy.get("banner_font_size") or (
                36 if strategy.get("banner_size") == "small" else (60 if strategy.get("banner_size") == "large" else 48)
            )
            scaled_title_size = int(banner_font_size * 1.0)
            t_font = _get_font(title_font_path, scaled_title_size)
            s_font = _get_font(sub_font_path, int(scaled_title_size * 0.65)) if sub_title else None

            # 加载并高精度生成真彩 🔥 Emoji 图标
            icon_h = max(18, int(scaled_title_size * 0.92))
            flame_img = _get_flame_icon(icon_h)
            icon_w = flame_img.width if flame_img else 0

            dummy = Image.new("RGBA", (1, 1))
            d = ImageDraw.Draw(dummy)
            t_bbox = d.textbbox((0, 0), title, font=t_font)
            t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]

            icon_gap = 12 if flame_img else 0
            title_row_w = icon_w + icon_gap + t_w

            s_w, s_h = 0, 0
            if s_font and sub_title:
                s_bbox = d.textbbox((0, 0), sub_title, font=s_font)
                s_w, s_h = s_bbox[2] - s_bbox[0], s_bbox[3] - s_bbox[1]

            content_w = max(title_row_w, s_w)
            pad_x = max(24, int(scaled_title_size * 0.95))
            pad_y = max(10, int(scaled_title_size * 0.38))

            # 胶囊底框尺寸：支持用户拖拽拉宽/自适应紧致贴合包裹文本
            banner_width_percent = strategy.get("banner_width_percent")
            if banner_width_percent:
                custom_w = int(target_w * float(banner_width_percent) / 100)
                box_w = min(int(target_w * 0.95), max(content_w + pad_x * 2, custom_w))
            else:
                box_w = min(int(target_w * 0.94), content_w + pad_x * 2)

            box_h = int((t_h + s_h + pad_y * 2 + 10) if sub_title else (t_h + pad_y * 2 + 6))

            banner_pos_x = strategy.get("banner_position_x")
            if banner_pos_x is None:
                banner_pos_x = 50
            banner_pos_y = strategy.get("banner_position_y")
            if banner_pos_y is None:
                banner_pos_y = 10 if has_watermark else 6

            # 水平居中基准点对齐前端 left: pos_x%; transform: translate(-50%, 0)
            banner_x = int(target_w * float(banner_pos_x) / 100 - box_w / 2)
            banner_x = max(16, min(target_w - box_w - 16, banner_x))
            banner_y = int(target_h * float(banner_pos_y) / 100)
            banner_y = max(10, min(target_h - box_h - 10, banner_y))

            # 绘制圆角胶囊深色底框 (与前端 bg-black/85 border-white/20 100% 吻合)
            draw.rounded_rectangle(
                [banner_x, banner_y, banner_x + box_w, banner_y + box_h],
                radius=box_h // 2,
                fill=(0, 0, 0, 215),
                outline=(255, 255, 255, 55),
                width=2
            )

            # 绘制 🔥 Emoji 与主标题
            t_row_x = banner_x + (box_w - title_row_w) // 2
            if sub_title:
                t_y = banner_y + pad_y
            else:
                t_y = banner_y + (box_h - t_h) // 2 - 1

            if flame_img:
                icon_y = t_y + (t_h - icon_h) // 2
                canvas.paste(flame_img, (t_row_x, icon_y), flame_img)

            draw.text((t_row_x + icon_w + icon_gap, t_y), title, font=t_font, fill=(255, 255, 255, 255))

            # 绘制金色副标语
            if sub_title and s_font:
                s_y = t_y + t_h + 8
                draw.text((banner_x + (box_w - s_w) // 2, s_y), sub_title, font=s_font, fill=(250, 204, 21, 255))

        # 2. 绘制品牌水印角标 (圆角微底框 + 纯白单行防搬运标识)
        if has_watermark:
            wm_text = str(strategy.get("watermark_text", "")).strip()
            opacity = float(strategy.get("watermark_opacity", 0.85))
            wm_font_size = strategy.get("watermark_font_size") or (
                24 if strategy.get("watermark_size") == "small" else (44 if strategy.get("watermark_size") == "large" else 34)
            )
            wm_font = _get_font(title_font_path, int(wm_font_size))

            dummy = Image.new("RGBA", (1, 1))
            d = ImageDraw.Draw(dummy)
            wm_bbox = d.textbbox((0, 0), wm_text, font=wm_font)
            wm_w, wm_h = wm_bbox[2] - wm_bbox[0], wm_bbox[3] - wm_bbox[1]
            wm_pad_x, wm_pad_y = 16, 8
            wm_box_w = wm_w + wm_pad_x * 2
            wm_box_h = wm_h + wm_pad_y * 2

            wm_pos_x = strategy.get("watermark_position_x")
            if wm_pos_x is None:
                wm_pos_x = 96 if (strategy.get("watermark_position") or "top_right").endswith("right") else 4
            wm_pos_y = strategy.get("watermark_position_y")
            if wm_pos_y is None:
                wm_pos_y = 96 if (strategy.get("watermark_position") or "top_right").startswith("bottom") else 3
            wm_x = int((target_w - wm_box_w) * float(wm_pos_x) / 100)
            wm_y = int((target_h - wm_box_h) * float(wm_pos_y) / 100)

            alpha_bg = max(40, min(220, int(160 * opacity)))
            alpha_text = max(80, min(255, int(255 * opacity)))
            draw.rounded_rectangle(
                [wm_x, wm_y, wm_x + wm_box_w, wm_y + wm_box_h],
                radius=10,
                fill=(0, 0, 0, alpha_bg),
                outline=(255, 255, 255, int(50 * opacity)),
                width=1
            )
            draw.text((wm_x + wm_pad_x, wm_y + wm_pad_y - 2), wm_text, font=wm_font, fill=(255, 255, 255, alpha_text))

        output_overlay_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_overlay_path, "PNG")
        return output_overlay_path

    def compose_jl_cut(
        self,
        talking_head_path: Path,
        broll_cuts: List[Dict[str, Any]],
        output_path: Path,
        aspect_ratio: str = "9:16",
        total_duration: float = 15.0,
        ass_subtitle_path: Optional[Path] = None,
        strategy: Optional[Dict[str, Any]] = None,
        kept_spans: Optional[List[Any]] = None,
        clean_base_output_path: Optional[Path] = None
    ) -> bool:
        """
        组装 FFmpeg filter_complex 管道：
        1. 若提供 kept_spans（粗剪有效片段序列），以 15ms afade 首尾防爆音无缝拼合音视频，空镜与字幕紧凑对齐。
        2. 保持口播主音频轨不变，指定时间区间将画面平替为 B-roll 空镜。
        3. 复合烧录 ASS 高级高亮字幕、顶部 Title 挂顶胶囊横幅与品牌水印角标。
        4. 采用 Lanczos 滤镜与 CRF 18 高清转码，保留真实色彩与画质。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        is_916 = aspect_ratio == "9:16"
        target_w = 1080 if is_916 else 1920
        target_h = 1920 if is_916 else 1080
        strat = strategy or {}
        speed = max(0.5, min(3.0, float(strat.get("video_speed") or 1.0)))
        is_sped = abs(speed - 1.0) >= 0.01

        th_is_hdr = self.is_hdr_video(talking_head_path)
        filter_preset = strat.get("filter_preset") or "clean_natural"
        filter_strength = float(strat.get("filter_strength") if strat.get("filter_strength") is not None else 1.0)
        th_filter = self.build_color_normalize_filter(
            th_is_hdr, target_w, target_h,
            filter_preset=filter_preset,
            filter_strength=filter_strength
        )

        # 生成无损透明图层
        overlay_png_path = output_path.parent / f"{output_path.stem}_overlay.png"
        has_overlay = bool(self.generate_overlay_canvas(target_w, target_h, strat, overlay_png_path))

        if not self.has_ffmpeg:
            # 真实执行铁律：缺少 FFmpeg 时严禁复制原文件假装合成成功，必须显式暴露失败
            overlay_png_path.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg 未安装或不可用，无法执行真实视频合成，已中止导出（未生成输出文件）")

        # -------------------------------------------------------------------------
        # 模式 A: 存在 kept_spans（粗剪智能切片 + 防爆音平滑拼接 + 紧凑时间轴合成）
        # -------------------------------------------------------------------------
        if kept_spans and len(kept_spans) > 0:
            inputs = ["-i", str(talking_head_path)]
            next_input_idx = 1
            filter_parts = []
            n_kept = len(kept_spans)

            for i, k in enumerate(kept_spans):
                st = round(float(getattr(k, "start_time", 0.0) if not isinstance(k, dict) else k.get("start_time", 0.0)), 3)
                et = round(float(getattr(k, "end_time", 0.0) if not isinstance(k, dict) else k.get("end_time", 0.0)), 3)
                dur = round(max(0.01, et - st), 3)
                fade = getattr(k, "audio_fade", True) if not isinstance(k, dict) else k.get("audio_fade", True)

                # 视频切片：仅执行时间裁剪，延迟到拼接后统一步骤执行画面重采样与调色锐化滤镜，
                # 将 O(N*F) 滤镜图暴涨降低为 O(F)，杜绝数十个切片重复实例化 Lanczos/Smartblur/CAS 导致的内存与图调度开销
                filter_parts.append(f"[0:v]trim=start={st}:end={et},setpts=PTS-STARTPTS[v_k{i}];")

                # 音频切片：首尾注入 15ms afade 平滑淡入淡出，消除硬切直流偏移音爆 (Pop Noise)；
                # aresample=async=1000 保证音频采样点毫秒级锁定物理时间戳，杜绝多段切片拼接导致的声画累积漂移
                if fade and dur >= 0.05:
                    fade_len = min(0.015, dur / 3.0)
                    fade_out_st = round(dur - fade_len, 3)
                    filter_parts.append(
                        f"[0:a]atrim=start={st}:end={et},asetpts=PTS-STARTPTS,aresample=async=1000,"
                        f"afade=t=in:ss=0:d={fade_len:.3f},afade=t=out:st={fade_out_st:.3f}:d={fade_len:.3f}[a_k{i}];"
                    )
                else:
                    filter_parts.append(f"[0:a]atrim=start={st}:end={et},asetpts=PTS-STARTPTS,aresample=async=1000[a_k{i}];")

            if n_kept == 1:
                filter_parts.append(f"[v_k0]{th_filter}[v_base];")
                current_v = "[v_base]"
                current_a = "[a_k0]"
            else:
                va_inputs = "".join(f"[v_k{i}][a_k{i}]" for i in range(n_kept))
                filter_parts.append(f"{va_inputs}concat=n={n_kept}:v=1:a=1[v_raw_base][a_base];")
                filter_parts.append(f"[v_raw_base]{th_filter}[v_base];")
                current_v = "[v_base]"
                current_a = "[a_base]"

            if is_sped:
                filter_parts.append(f"{current_v}setpts=(1.0/{speed})*PTS[v_sped];")
                filter_parts.append(f"{current_a}{_build_atempo_chain(speed)}[a_sped];")
                current_v = "[v_sped]"
                current_a = "[a_sped]"

            # 处理 B-roll (已重投影至紧凑时间轴)
            if broll_cuts:
                fade_mode = str(strat.get("transition_style") or "cut") == "fade"
                eff_broll_cuts = [
                    {
                        **b,
                        "start_time": round(float(b["start_time"]) / speed, 3) if is_sped else float(b["start_time"]),
                        "end_time": round(float(b["end_time"]) / speed, 3) if is_sped else float(b["end_time"]),
                        "transition": b.get("transition", 0.0)
                    }
                    for b in broll_cuts
                ]
                for i, b in enumerate(eff_broll_cuts):
                    broll_file = b.get("material_path")
                    if broll_file and Path(broll_file).exists():
                        b_st = round(float(b["start_time"]), 3)
                        b_et = round(float(b["end_time"]), 3)
                        b_dur = round(b_et - b_st, 3)
                        if b_dur > 0.05:
                            b_idx = next_input_idx
                            next_input_idx += 1
                            inputs.extend(["-i", str(broll_file)])
                            b_hdr = self.is_hdr_video(Path(broll_file))
                            b_norm = self.build_color_normalize_filter(b_hdr, target_w, target_h, filter_preset="original")
                            b_source_st = round(float(b.get("source_start_time", 0.0) or 0.0), 3)
                            fade_filter = ""
                            if fade_mode and float(b.get("transition", 0.0)) > 0:
                                trans = min(0.5, float(b["transition"]), b_dur / 3.0)
                                fade_filter = f",fade=t=in:st=0:d={trans:.3f}:alpha=1,fade=t=out:st={round(b_dur - trans, 3):.3f}:d={trans:.3f}:alpha=1"
                            filter_parts.append(f"[{b_idx}:v]trim=start={b_source_st:.3f}:duration={b_dur:.3f},setpts=PTS-STARTPTS+{b_st:.3f}/TB,{b_norm}{fade_filter}[b_seg{i}];")
                            filter_parts.append(f"{current_v}[b_seg{i}]overlay=0:0:enable='between(t,{b_st:.3f},{b_et:.3f})':eof_action=repeat[v_over{i}];")
                            current_v = f"[v_over{i}]"

            clean_v_tag = None
            clean_a_map = ["-map", current_a]
            sub_a_map = ["-map", current_a]

            if clean_base_output_path:
                clean_base_output_path.parent.mkdir(parents=True, exist_ok=True)
                clean_v_tag = "[v_clean_export]"
                filter_parts.append(f"{current_v}split=2{clean_v_tag}[v_for_sub];")
                filter_parts.append(f"{current_a}asplit=2[a_clean_export][a_sub_export];")
                current_v = "[v_for_sub]"
                clean_a_map = ["-map", "[a_clean_export]"]
                sub_a_map = ["-map", "[a_sub_export]"]

            # 烧录 ASS 字幕
            if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
                escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
                filter_parts.append(f"{current_v}ass='{escaped_ass}'[v_sub];")
                current_v = "[v_sub]"

            # 顶部横幅与水印图层
            if has_overlay:
                overlay_idx = next_input_idx
                next_input_idx += 1
                inputs.extend(["-i", str(overlay_png_path)])
                filter_parts.append(f"{current_v}[{overlay_idx}:v]overlay=0:0[v_out];")
                current_v = "[v_out]"

            full_filter = "".join(filter_parts).rstrip(";")

            cmd = [
                "ffmpeg", "-y",
                "-threads", "0", "-filter_threads", "0",
                *inputs,
                "-filter_complex", full_filter,
            ]

            if clean_base_output_path and clean_v_tag:
                cmd.extend([
                    "-map", clean_v_tag,
                    *clean_a_map,
                    *self.get_video_encode_args(),
                    "-c:a", "aac",
                    "-b:a", "320k",
                    "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709",
                    "-color_trc", "bt709",
                    "-colorspace", "bt709",
                    "-movflags", "+faststart",
                    str(clean_base_output_path)
                ])

            cmd.extend([
                "-map", current_v,
                *sub_a_map,
                *self.get_video_encode_args(),
                "-c:a", "aac",
                "-b:a", "320k",
                "-pix_fmt", "yuv420p",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-movflags", "+faststart",
                str(output_path)
            ])

            try:
                res = self._run_ffmpeg_with_cpu_fallback(cmd, timeout=300)
                if res.returncode == 0:
                    return True
                err_str = res.stderr.decode("utf-8", errors="replace")
                print(f"[FFmpegFilterComposer] Kept spans render failed (exit {res.returncode}): {err_str[-300:]}")
                if talking_head_path.stat().st_size > 10240:
                    raise RuntimeError(f"FFmpeg 粗剪压制失败 (exit {res.returncode}): {err_str[-200:]}")
                shutil.copyfile(str(talking_head_path), str(output_path))
                return True
            except Exception as e:
                if talking_head_path.stat().st_size > 10240:
                    print(f"[FFmpegFilterComposer] Kept spans render exception: {e}")
                    raise
                shutil.copyfile(str(talking_head_path), str(output_path))
                return True
            finally:
                overlay_png_path.unlink(missing_ok=True)

        # 单一视频流快速高清转码管道 (无空镜平替时)
        if not broll_cuts:
            inputs = ["-i", str(talking_head_path)]
            filter_chain = []
            if not is_sped:
                filter_chain.append(f"[0:v]{th_filter}[v_scaled]")
                clean_a_map = ["-map", "0:a?"]
                sub_a_map = ["-map", "0:a?"]
            else:
                filter_chain.append(f"[0:v]setpts=(1.0/{speed})*PTS,{th_filter}[v_scaled]")
                if clean_base_output_path:
                    filter_chain.append(f"[0:a]{_build_atempo_chain(speed)},asplit=2[a_clean_export][a_sub_export]")
                    clean_a_map = ["-map", "[a_clean_export]"]
                    sub_a_map = ["-map", "[a_sub_export]"]
                else:
                    filter_chain.append(f"[0:a]{_build_atempo_chain(speed)}[a_sped]")
                    clean_a_map = ["-map", "[a_sped]"]
                    sub_a_map = ["-map", "[a_sped]"]
            current_v = "[v_scaled]"

            clean_v_tag = None
            if clean_base_output_path:
                clean_base_output_path.parent.mkdir(parents=True, exist_ok=True)
                clean_v_tag = "[v_clean_export]"
                filter_chain.append(f"{current_v}split=2{clean_v_tag}[v_for_sub]")
                current_v = "[v_for_sub]"

            if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
                escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
                filter_chain.append(f"{current_v}ass='{escaped_ass}'[v_sub]")
                current_v = "[v_sub]"

            if has_overlay:
                inputs.extend(["-i", str(overlay_png_path)])
                filter_chain.append(f"{current_v}[1:v]overlay=0:0[v_out]")
                current_v = "[v_out]"

            cmd = [
                "ffmpeg", "-y",
                "-threads", "0", "-filter_threads", "0",
                *inputs,
                "-filter_complex", ";".join(filter_chain),
            ]

            if clean_base_output_path and clean_v_tag:
                cmd.extend([
                    "-map", clean_v_tag,
                    *clean_a_map,
                    *self.get_video_encode_args(),
                    "-c:a", "aac",
                    "-b:a", "320k",
                    "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709",
                    "-color_trc", "bt709",
                    "-colorspace", "bt709",
                    "-movflags", "+faststart",
                    str(clean_base_output_path)
                ])

            cmd.extend([
                "-map", current_v,
                *sub_a_map,
                *self.get_video_encode_args(),
                "-c:a", "aac",
                "-b:a", "320k",
                "-pix_fmt", "yuv420p",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-movflags", "+faststart",
                str(output_path)
            ])

            try:
                res = self._run_ffmpeg_with_cpu_fallback(cmd, timeout=90)
                if res.returncode == 0:
                    return True

                err_str = res.stderr.decode("utf-8", errors="replace")
                print(f"[FFmpegFilterComposer] Single transcode failed (exit {res.returncode}): {err_str[-300:]}")
                if talking_head_path.stat().st_size > 10240:
                    return False
                shutil.copyfile(str(talking_head_path), str(output_path))
                return True
            finally:
                overlay_png_path.unlink(missing_ok=True)

        # 构建多输入与 filter_complex 滤镜链 (空镜混合模式)
        inputs = ["-i", str(talking_head_path)]
        fade_mode = str(strat.get("transition_style") or "cut") == "fade"
        # fade 档相邻转场下限：xfade duration 必须为正，接近 0 时视觉上即为硬切
        MIN_FADE = 0.04

        # 1. 计算缩放后总时长与空镜切片 (倍速对齐)
        eff_total_duration = (total_duration / speed) if is_sped else total_duration
        if is_sped:
            eff_broll_cuts = [
                {
                    **b,
                    "start_time": round(float(b["start_time"]) / speed, 3),
                    "end_time": round(float(b["end_time"]) / speed, 3),
                    "transition": b.get("transition", 0.0)
                }
                for b in broll_cuts
            ]
        else:
            eff_broll_cuts = broll_cuts

        # 2. 构建片段序列：{"input_idx", "trim_start", "base_dur", "is_broll", "transition"}
        segs = []
        sorted_cuts = sorted(eff_broll_cuts, key=lambda x: x["start_time"])
        current_time = 0.0
        for cut in sorted_cuts:
            start = cut["start_time"]
            end = cut["end_time"]
            broll_file = cut.get("material_path")
            if end <= current_time:
                continue
            if start > current_time:
                segs.append({
                    "kind": "talking", "input_idx": 0,
                    "trim_start": current_time, "base_dur": start - current_time,
                    "transition": 0.0,
                })
            if broll_file and Path(broll_file).exists():
                segs.append({
                    "kind": "broll", "input_idx": None,
                    "trim_start": round(float(cut.get("source_start_time", 0.0) or 0.0), 3),
                    "base_dur": end - start,
                    "transition": max(0.0, min(0.5, float(cut.get("transition") or 0.0))),
                    "path": str(broll_file),
                })
            current_time = end
        if current_time < eff_total_duration:
            segs.append({
                "kind": "talking", "input_idx": 0,
                "trim_start": current_time, "base_dur": eff_total_duration - current_time,
                "transition": 0.0,
            })

        # 3. fade 档：先按衔接点计算转场时长，并由 broll 侧补帧（trim 延长）抵消叠化消耗，
        #    保证与口播音轨总时长严格对齐；衔接点两侧都不是 broll 的情况不存在（concat 结构决定）
        junction_fades: List[float] = []
        if fade_mode and len(segs) >= 2:
            for j in range(1, len(segs)):
                prev_seg, cur_seg = segs[j - 1], segs[j]
                f = cur_seg["transition"] if cur_seg["kind"] == "broll" else prev_seg["transition"]
                f = max(MIN_FADE, min(0.5, f))
                junction_fades.append(f)
                if cur_seg["kind"] == "broll":
                    cur_seg["base_dur"] += f
                elif prev_seg["kind"] == "broll":
                    prev_seg["base_dur"] += f

        # 4. 片段进滤镜：登记输入、trim+scale，得到 [v_segN] 标签
        filter_parts = []
        concat_inputs = []
        seg_labels = []
        next_input_idx = 1
        for i, seg in enumerate(segs):
            if seg["kind"] == "broll":
                seg["input_idx"] = next_input_idx
                next_input_idx += 1
                # 消除全局无限循环解码 (-stream_loop -1)，按需载入素材
                inputs.extend(["-i", seg["path"]])
                broll_is_hdr = self.is_hdr_video(Path(seg["path"]))
                broll_filter = self.build_color_normalize_filter(broll_is_hdr, target_w, target_h)
                filter_parts.append(
                    f"[{seg['input_idx']}:v]trim=start={seg['trim_start']}:duration={seg['base_dur']},setpts=PTS-STARTPTS,{broll_filter}[v_seg{i}];"
                )
            else:
                if is_sped:
                    orig_start = round(seg['trim_start'] * speed, 3)
                    orig_dur = round(seg['base_dur'] * speed, 3)
                    filter_parts.append(
                        f"[{seg['input_idx']}:v]trim=start={orig_start}:duration={orig_dur},setpts=(1.0/{speed})*(PTS-STARTPTS),{th_filter}[v_seg{i}];"
                    )
                else:
                    filter_parts.append(
                        f"[{seg['input_idx']}:v]trim=start={seg['trim_start']}:duration={seg['base_dur']},setpts=PTS-STARTPTS,{th_filter}[v_seg{i}];"
                    )
            seg_labels.append(f"[v_seg{i}]")

        # 5. 片段串联：fade 档用 xfade 链（duration=衔接转场，offset=累计显示时长）；
        #    cut 档保持 concat 硬切。
        if fade_mode and len(segs) >= 2:
            display = [
                segs[i]["base_dur"]
                - (junction_fades[i - 1] if i > 0 else 0.0)
                - (junction_fades[i] if i < len(junction_fades) else 0.0)
                for i in range(len(segs))
            ]
            current_label = seg_labels[0]
            cum = display[0]
            for j in range(1, len(segs)):
                out_label = f"[vx{j}]"
                off = max(0.0, cum - junction_fades[j - 1])
                filter_parts.append(
                    f"{current_label}{seg_labels[j]}xfade=transition=fade:duration={junction_fades[j - 1]:.3f}:offset={off:.3f}{out_label};"
                )
                current_label = out_label
                cum = cum + display[j] - junction_fades[j - 1]
            current_v = current_label
            full_filter = "".join(filter_parts).rstrip(";")
        else:
            for label in seg_labels:
                concat_inputs.append(label)
            n_segs = len(concat_inputs)
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={n_segs}:v=1:a=0[v_concat];")
            current_v = "[v_concat]"
            full_filter = "".join(filter_parts).rstrip(";")

        clean_v_tag = None
        if clean_base_output_path:
            clean_base_output_path.parent.mkdir(parents=True, exist_ok=True)
            clean_v_tag = "[v_clean_export]"
            full_filter += f";{current_v}split=2{clean_v_tag}[v_for_sub]"
            current_v = "[v_for_sub]"

        if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
            escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
            full_filter += f";{current_v}ass='{escaped_ass}'[v_sub]"
            current_v = "[v_sub]"

        if has_overlay:
            overlay_idx = next_input_idx
            next_input_idx += 1
            inputs.extend(["-i", str(overlay_png_path)])
            full_filter += f";{current_v}[{overlay_idx}:v]overlay=0:0[v_out]"
            current_v = "[v_out]"

        clean_a_map = ["-map", "0:a"]
        sub_a_map = ["-map", "0:a"]
        if is_sped:
            if clean_base_output_path and clean_v_tag:
                full_filter += f";[0:a]{_build_atempo_chain(speed)},asplit=2[a_clean_export][a_sub_export]"
                clean_a_map = ["-map", "[a_clean_export]"]
                sub_a_map = ["-map", "[a_sub_export]"]
            else:
                full_filter += f";[0:a]{_build_atempo_chain(speed)}[a_sped]"
                clean_a_map = ["-map", "[a_sped]"]
                sub_a_map = ["-map", "[a_sped]"]

        cmd = [
            "ffmpeg", "-y",
            "-threads", "0", "-filter_threads", "0",
            *inputs,
            "-filter_complex", full_filter,
        ]

        if clean_base_output_path and clean_v_tag:
            cmd.extend([
                "-map", clean_v_tag,
                *clean_a_map,
                *self.get_video_encode_args(),
                "-c:a", "aac",
                "-b:a", "320k",
                "-pix_fmt", "yuv420p",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-movflags", "+faststart",
                str(clean_base_output_path)
            ])

        cmd.extend([
            "-map", current_v,
            *sub_a_map,
            *self.get_video_encode_args(),
            "-c:a", "aac",
            "-b:a", "320k",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-movflags", "+faststart",
            str(output_path)
        ])

        try:
            res = self._run_ffmpeg_with_cpu_fallback(cmd, timeout=300)
            if res.returncode == 0:
                return True

            err_str = res.stderr.decode("utf-8", errors="replace")
            print(f"[FFmpegFilterComposer] Complex render failed (exit {res.returncode}): {err_str[-300:]}")
            if talking_head_path.stat().st_size > 10240:
                raise RuntimeError(f"FFmpeg 导出失败 (exit {res.returncode}): {err_str[-200:]}")
            shutil.copyfile(str(talking_head_path), str(output_path))
            return True
        except Exception as e:
            if talking_head_path.stat().st_size > 10240:
                print(f"[FFmpegFilterComposer] Complex render exception: {e}")
                raise
            shutil.copyfile(str(talking_head_path), str(output_path))
            return True
        finally:
            overlay_png_path.unlink(missing_ok=True)

    def compose_clean_base(
        self,
        talking_head_path: Path,
        broll_cuts: List[Dict[str, Any]],
        output_path: Path,
        aspect_ratio: str = "9:16",
        total_duration: float = 15.0,
        strategy: Optional[Dict[str, Any]] = None,
        kept_spans: Optional[List[Any]] = None
    ) -> bool:
        """
        合成无字幕、无横幅水印的高清底包（含粗剪有效片段拼接、防爆音 afade、画质增强滤镜与 B-roll 空镜平替）：
        作为分层重合成的权威底包缓存，避免修改字幕时重复进行昂贵的切片与磨皮重编码。
        """
        clean_strat = dict(strategy or {})
        clean_strat["show_subtitles"] = False
        clean_strat["enable_banner"] = False
        clean_strat["enable_watermark"] = False
        return self.compose_jl_cut(
            talking_head_path=talking_head_path,
            broll_cuts=broll_cuts,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
            total_duration=total_duration,
            ass_subtitle_path=None,
            strategy=clean_strat,
            kept_spans=kept_spans
        )

    def burn_subtitles_and_overlay_fast(
        self,
        clean_base_path: Path,
        output_path: Path,
        ass_subtitle_path: Optional[Path] = None,
        strategy: Optional[Dict[str, Any]] = None,
        aspect_ratio: str = "9:16"
    ) -> bool:
        """
        极速烧录字幕与动态横幅/水印图层（针对分层底包复用场景）：
        输入已预渲染好的无字幕无横幅高清底包 (_clean_base.mp4)，
        直接将 ASS 字幕滤镜与透明 PNG 叠加在视频流上，音频轨执行 -c:a copy 零重编码，
        耗时从 40~60s 骤降至 1~2s。
        """
        if not self.has_ffmpeg:
            raise RuntimeError("FFmpeg 未安装或不可用，无法执行极速烧录")
        if not clean_base_path.exists() or clean_base_path.stat().st_size == 0:
            raise FileNotFoundError(f"底包视频文件不存在或为空: {clean_base_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        is_916 = aspect_ratio == "9:16"
        target_w = 1080 if is_916 else 1920
        target_h = 1920 if is_916 else 1080
        strat = strategy or {}

        overlay_png_path = output_path.parent / f"{output_path.stem}_fast_overlay.png"
        has_overlay = bool(self.generate_overlay_canvas(target_w, target_h, strat, overlay_png_path))

        inputs = ["-i", str(clean_base_path)]
        filter_parts = []
        current_v = "[0:v]"

        if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
            escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
            filter_parts.append(f"{current_v}ass='{escaped_ass}'[v_sub]")
            current_v = "[v_sub]"

        if has_overlay:
            overlay_idx = len(inputs) // 2
            inputs.extend(["-i", str(overlay_png_path)])
            filter_parts.append(f"{current_v}[{overlay_idx}:v]overlay=0:0[v_out]")
            current_v = "[v_out]"

        cmd = ["ffmpeg", "-y", "-threads", "0", "-filter_threads", "0", *inputs]
        if filter_parts:
            cmd.extend(["-filter_complex", ";".join(filter_parts), "-map", current_v])
        else:
            cmd.extend(["-map", "0:v"])

        cmd.extend([
            "-map", "0:a?",
            *self.get_video_encode_args(),
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-movflags", "+faststart",
            str(output_path)
        ])

        try:
            res = self._run_ffmpeg_with_cpu_fallback(cmd, timeout=120)
            if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return True
            err_str = res.stderr.decode("utf-8", errors="replace")
            print(f"[FFmpegFilterComposer] Fast burn failed (exit {res.returncode}): {err_str[-300:]}")
            if clean_base_path.stat().st_size > 10240:
                raise RuntimeError(f"FFmpeg 极速烧录失败 (exit {res.returncode}): {err_str[-200:]}")
            shutil.copyfile(str(clean_base_path), str(output_path))
            return True
        finally:
            overlay_png_path.unlink(missing_ok=True)

composer = FFmpegFilterComposer()


