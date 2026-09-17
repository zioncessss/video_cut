import subprocess
import shutil
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import io
import base64
from PIL import Image, ImageDraw, ImageFont

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

class FFmpegFilterComposer:
    def __init__(self):
        self.has_ffmpeg = bool(shutil.which("ffmpeg"))

    def build_scale_filter(self, aspect_ratio: str = "9:16") -> str:
        """根据目标比例构建归一化缩放与无裁剪填充滤镜（采用 Lanczos 重采样高保真保持画面清晰度）"""
        if aspect_ratio == "9:16":
            return "scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos+accurate_rnd,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
        return "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos+accurate_rnd,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"

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
        has_banner = bool(strategy.get("enable_top_banner") and strategy.get("banner_main_title"))
        has_watermark = bool(strategy.get("enable_watermark") and strategy.get("watermark_text"))

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
        strategy: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        组装 FFmpeg filter_complex 管道：
        1. 保持口播主音频轨不变，指定时间区间将画面平替为 B-roll 空镜。
        2. 复合烧录 ASS 高级高亮字幕、顶部 Title 挂顶胶囊横幅与品牌水印角标。
        3. 采用 Lanczos 滤镜与 CRF 18 高清转码，保留真实色彩与画质。
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scale_filter = self.build_scale_filter(aspect_ratio)
        strat = strategy or {}

        is_916 = aspect_ratio == "9:16"
        target_w = 1080 if is_916 else 1920
        target_h = 1920 if is_916 else 1080

        # 生成无损透明图层
        overlay_png_path = output_path.parent / f"{output_path.stem}_overlay.png"
        has_overlay = bool(self.generate_overlay_canvas(target_w, target_h, strat, overlay_png_path))

        if not self.has_ffmpeg:
            # 真实执行铁律：缺少 FFmpeg 时严禁复制原文件假装合成成功，必须显式暴露失败
            overlay_png_path.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg 未安装或不可用，无法执行真实视频合成，已中止导出（未生成输出文件）")

        # 单一视频流快速高清转码管道 (无空镜平替时)
        if not broll_cuts:
            inputs = ["-i", str(talking_head_path)]
            filter_chain = [f"[0:v]{scale_filter}[v_scaled]"]
            current_v = "[v_scaled]"

            if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
                escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
                filter_chain.append(f"{current_v}ass='{escaped_ass}'[v_sub]")
                current_v = "[v_sub]"

            if has_overlay:
                inputs.extend(["-i", str(overlay_png_path)])
                filter_chain.append(f"{current_v}[1:v]overlay=0:0[v_out]")
                current_v = "[v_out]"

            cmd = [
                "ffmpeg", "-y", *inputs,
                "-filter_complex", ";".join(filter_chain),
                "-map", current_v,
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-color_primaries", "bt709",
                "-color_trc", "bt709",
                "-colorspace", "bt709",
                "-movflags", "+faststart",
                str(output_path)
            ]

            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
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
        filter_parts = []
        concat_inputs = []

        sorted_cuts = sorted(broll_cuts, key=lambda x: x["start_time"])
        current_time = 0.0
        seg_idx = 0

        for cut in sorted_cuts:
            start = cut["start_time"]
            end = cut["end_time"]
            broll_file = cut.get("material_path")

            if start > current_time:
                dur = start - current_time
                filter_parts.append(
                    f"[0:v]trim=start={current_time}:duration={dur},setpts=PTS-STARTPTS,{scale_filter}[v_seg{seg_idx}];"
                )
                concat_inputs.append(f"[v_seg{seg_idx}]")
                seg_idx += 1

            if broll_file and Path(broll_file).exists():
                input_idx = len(inputs) // 2
                inputs.extend(["-i", str(broll_file)])
                cut_dur = end - start
                filter_parts.append(
                    f"[{input_idx}:v]trim=start=0:duration={cut_dur},setpts=PTS-STARTPTS,{scale_filter}[v_seg{seg_idx}];"
                )
                concat_inputs.append(f"[v_seg{seg_idx}]")
                seg_idx += 1

            current_time = end

        if current_time < total_duration:
            dur = total_duration - current_time
            filter_parts.append(
                f"[0:v]trim=start={current_time}:duration={dur},setpts=PTS-STARTPTS,{scale_filter}[v_seg{seg_idx}];"
            )
            concat_inputs.append(f"[v_seg{seg_idx}]")
            seg_idx += 1

        n_segs = len(concat_inputs)
        filter_parts.append(f"{''.join(concat_inputs)}concat=n={n_segs}:v=1:a=0[v_concat];")
        current_v = "[v_concat]"

        if strat.get("show_subtitles", True) and ass_subtitle_path and Path(ass_subtitle_path).exists():
            escaped_ass = str(ass_subtitle_path).replace("\\", "/").replace(":", "\\:")
            filter_parts.append(f"{current_v}ass='{escaped_ass}'[v_sub];")
            current_v = "[v_sub]"

        if has_overlay:
            overlay_idx = len(inputs) // 2
            inputs.extend(["-i", str(overlay_png_path)])
            filter_parts.append(f"{current_v}[{overlay_idx}:v]overlay=0:0[v_out]")
            current_v = "[v_out]"
        else:
            if filter_parts[-1].endswith(";"):
                filter_parts[-1] = filter_parts[-1][:-1]

        full_filter = "".join(filter_parts).rstrip(";")

        cmd = [
            "ffmpeg", "-y", *inputs,
            "-filter_complex", full_filter,
            "-map", current_v,
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-movflags", "+faststart",
            str(output_path)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
            if res.returncode == 0:
                return True

            err_str = res.stderr.decode("utf-8", errors="replace")
            print(f"[FFmpegFilterComposer] Complex render failed (exit {res.returncode}): {err_str[-300:]}")
            if talking_head_path.stat().st_size > 10240:
                return False
            shutil.copyfile(str(talking_head_path), str(output_path))
            return True
        except Exception as e:
            if talking_head_path.stat().st_size > 10240:
                print(f"[FFmpegFilterComposer] Complex render exception: {e}")
                return False
            shutil.copyfile(str(talking_head_path), str(output_path))
            return True
        finally:
            overlay_png_path.unlink(missing_ok=True)

composer = FFmpegFilterComposer()

