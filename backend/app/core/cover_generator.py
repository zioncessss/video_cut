"""012: 视频封面生成与比例自适应渲染引擎（6 大实战模板升级版）。

提供口播封面模板合成（双层描边贴纸大字 / 上下通栏权威撞色条 / 拱形包头彩虹字 /
胸前羽化白光沉浸字 / 倾角冲击引流标 / 极简轻奢杂志风）、4 套高转化调色盘、
高斯模糊背景填充自适应算法以及候选帧智能提取。
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.models.entities import CoverDesignConfig

logger = logging.getLogger(__name__)

# 标准短视频 9:16 分辨率
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# ---------------------------------------------------------------------------
# 4 套高转化调色盘（research.md §4 + 真实爆款账号风格调优：更舒适耐看的搭配）
# ---------------------------------------------------------------------------
COVER_PALETTES: Dict[str, Dict[str, str]] = {
    "classic_blue": {"name": "蓝白清爽", "main": "#2E7CD6", "sub": "#FFFFFF", "accent": "#124CD6"},
    "authority_red": {"name": "国潮权威红", "main": "#B91C1C", "sub": "#FFFFFF", "accent": "#0F172A"},
    "sunset_orange": {"name": "暖阳橙金", "main": "#F97316", "sub": "#FFFFFF", "accent": "#7C2D12"},
    "frost_burgundy": {"name": "雪白羽化酒红", "main": "#991B1B", "sub": "#FFFFFF", "accent": "#FDE047"},
    "neon_lime": {"name": "荧光黄绿 3D", "main": "#DBFA11", "sub": "#2A5101", "accent": "#FFFFFF"},
}

# 旧调色盘标识 → 新调色盘映射（存量工程向后兼容渲染，统一迁移到更舒适配色）
_LEGACY_PALETTE_ALIASES: Dict[str, str] = {
    "neon_cyber": "classic_blue",
    "hot_pink_gold": "sunset_orange",
}

# 旧版配色主题（存量工程向后兼容渲染）
_LEGACY_COLOR_MAP: Dict[str, Dict[str, str]] = {
    "yellow_black": {"primary": "#FACC15", "secondary": "#FFFFFF", "badge_bg": "#18181B", "badge_fg": "#FACC15"},
    "red_white": {"primary": "#EF4444", "secondary": "#FFFFFF", "badge_bg": "#EF4444", "badge_fg": "#FFFFFF"},
    "blue_white": {"primary": "#38BDF8", "secondary": "#FFFFFF", "badge_bg": "#0284C7", "badge_fg": "#FFFFFF"},
    "white_yellow": {"primary": "#FFFFFF", "secondary": "#FACC15", "badge_bg": "#FACC15", "badge_fg": "#18181B"},
    "white_red": {"primary": "#FFFFFF", "secondary": "#EF4444", "badge_bg": "#EF4444", "badge_fg": "#FFFFFF"},
    "clean_white": {"primary": "#FFFFFF", "secondary": "#E2E8F0", "badge_bg": "#1E293B", "badge_fg": "#FFFFFF"},
    "clean_gold": {"primary": "#FDE047", "secondary": "#FFFFFF", "badge_bg": "#854D0E", "badge_fg": "#FEF08A"},
}

# 6 大实战模板目录（contracts/cover-api.md 契约定义，含旧 4 模板以外的全部新模板）
COVER_TEMPLATES_CATALOG = [
    {
        "id": "sticker_double_stroke",
        "name": "双层描边贴纸大字",
        "category": "local_hook",
        "badge": "👑 爆款首选",
        "sample_preview": "武义学车款",
        "description": "顶部超大双层描边（黑描边+纯白贴纸厚边），底部手势指示胶囊与荧光引导字",
        "supported_themes": ["classic_blue", "authority_red", "sunset_orange"]
    },
    {
        "id": "split_contrast_bar",
        "name": "上下通栏权威撞色条",
        "category": "authority_banner",
        "badge": "🏛️ 权威正规",
        "sample_preview": "杭州学车款",
        "description": "顶部全宽红底横条白字，中间人物实景，底部全宽白底横条深红大字痛点",
        "supported_themes": ["authority_red", "frost_burgundy"]
    },
    {
        "id": "rainbow_arc_header",
        "name": "拱形包头彩虹字",
        "category": "curved_impact",
        "badge": "⚡ 同城爆款",
        "sample_preview": "金华金东款",
        "description": "向上彩虹拱形包头弧字，不挡人脸环抱发顶，配手写疑问句与斜角账号标",
        "supported_themes": ["sunset_orange", "classic_blue"]
    },
    {
        "id": "bottom_fog_vignette",
        "name": "胸前羽化白光沉浸字",
        "category": "vignette_focus",
        "badge": "✨ 高级清透",
        "sample_preview": "婺城学车款",
        "description": "底部柔和白色羽化遮罩自然弱化杂乱环境，胸前排布立体深红白边特大字",
        "supported_themes": ["frost_burgundy", "authority_red"]
    },
    {
        "id": "angled_impact_stamp",
        "name": "倾角冲击引流标",
        "category": "angled_stamp",
        "badge": "💥 强烈冲击",
        "sample_preview": "绍兴学车款",
        "description": "顶部 -10° 动感微倾斜大字贴纸，右侧双行紧凑金句，底部实色警示横条",
        "supported_themes": ["authority_red", "sunset_orange"]
    },
    {
        "id": "clean_editorial",
        "name": "极简轻奢杂志风",
        "category": "editorial",
        "badge": "📖 知性轻奢",
        "sample_preview": "小红书爆款",
        "description": "轻奢英文章节标、纤细纯白大字、细横线与衬线副标，高级留白",
        "supported_themes": ["frost_burgundy"]
    },
    {
        "id": "text_behind_person",
        "name": "同城爆款三段贴纸大字",
        "category": "local_burst",
        "badge": "🔥 顶流同款",
        "sample_preview": "兔牙教练同款",
        "description": "顶部拱形微弧大字 + 胸前引导小标 + 底部亮黄转化大字，单字独立黄金微隙，原汁原味真实画面",
        "supported_themes": ["classic_blue", "authority_red", "sunset_orange"]
    },
    {
        "id": "neon_3d_sticker",
        "name": "荧光绿 3D 贴纸大字",
        "category": "local_burst",
        "badge": "⚡ 顶流爆款",
        "sample_preview": "女生学车/倒车入库款",
        "description": "顶部拱形微弧荧光黄绿大字 + 实体3D深绿挤压厚度 + 纯白副标与转化大字 + 纯白手绘高光涂鸦",
        "supported_themes": ["neon_lime", "classic_blue", "authority_red"]
    }
]

# 旧模板仅保留渲染兼容，不再出现在模板目录中
LEGACY_TEMPLATE_IDS = {"gold_bold", "color_badge", "dual_contrast"}

# ---------------------------------------------------------------------------
# 4 大字系候选链（Windows / macOS 双端探测，缺失逐级回退默认黑体）
# ---------------------------------------------------------------------------
_FONT_FAMILY_CANDIDATES: Dict[str, Dict[bool, List[str]]] = {
    "heavy_gothic": {
        True: ["msyhbd.ttc", "simhei.ttf", "msyh.ttc"],
        False: ["msyh.ttc", "simhei.ttf", "simsun.ttc"],
    },
    "brush_kai": {
        True: ["STKAITI.TTF", "simkai.ttf", "msyhbd.ttc"],
        False: ["STKAITI.TTF", "simkai.ttf", "msyh.ttc"],
    },
    "handwriting_tilt": {
        True: ["STXINGKA.TTF", "STKAITI.TTF", "simkai.ttf", "msyhbd.ttc"],
        False: ["STXINGKA.TTF", "STKAITI.TTF", "simkai.ttf", "msyh.ttc"],
    },
    "editorial_serif": {
        True: ["simsun.ttc", "STZHONGS.TTF", "msyhbd.ttc"],
        False: ["simsun.ttc", "msyh.ttc"],
    },
}

_MAC_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Kaiti.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def _find_system_font(bold: bool = True, family: str = "heavy_gothic") -> str:
    """按平台与字系探测中文字体，逐级回退保证永不中断渲染"""
    candidates: List[Path] = []
    named = _FONT_FAMILY_CANDIDATES.get(family, _FONT_FAMILY_CANDIDATES["heavy_gothic"]).get(bold, [])
    if os.name == "nt":
        windir = os.environ.get("WINDIR", "C:\\Windows")
        fonts_dir = Path(windir) / "Fonts"
        candidates.extend(fonts_dir / name for name in named)
        # 字系专属字体缺失时回退基础黑体链
        candidates.extend([
            fonts_dir / "msyhbd.ttc",
            fonts_dir / "simhei.ttf",
            fonts_dir / "msyh.ttc",
            fonts_dir / "simsun.ttc",
        ])
    else:
        candidates.extend(Path(p) for p in _MAC_FONT_CANDIDATES)

    for font_path in candidates:
        if font_path.exists():
            return str(font_path)
    return ""


def get_font(
    size: int,
    bold: bool = True,
    family: str = "heavy_gothic"
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """加载中文字体（按 4 大字系候选链），失败时优雅回退 PIL 默认字体"""
    font_path = _find_system_font(bold=bold, family=family)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception as e:
            logger.warning("加载系统字体失败 %s: %s", font_path, e)
    return ImageFont.load_default(size)


def adapt_image_aspect_ratio(
    image_input: Union[Image.Image, Path, str],
    target_size: Tuple[int, int] = (TARGET_WIDTH, TARGET_HEIGHT),
    mode: str = "blur_padding"
) -> Image.Image:
    """
    将任意比例图片适配至目标尺寸（默认 1080x1920 9:16）。

    :param image_input: PIL Image 或 图片路径
    :param target_size: (目标宽, 目标高)
    :param mode: "blur_padding" (高斯模糊背景填充) | "center_crop" (居中等比裁切)
    """
    if isinstance(image_input, (str, Path)):
        img = Image.open(str(image_input)).convert("RGBA")
    else:
        img = image_input.convert("RGBA")

    tw, th = target_size
    orig_w, orig_h = img.size

    if orig_w == tw and orig_h == th:
        return img

    if mode == "center_crop":
        # 居中等比裁切
        scale = max(tw / orig_w, th / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    # 默认 blur_padding：高斯模糊背景填充
    # 1. 生成底图：放大铺满并重度模糊 + 微调暗
    bg_scale = max(tw / orig_w, th / orig_h)
    bg_w = int(orig_w * bg_scale)
    bg_h = int(orig_h * bg_scale)
    bg = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    bg_left = (bg_w - tw) // 2
    bg_top = (bg_h - th) // 2
    bg_cropped = bg.crop((bg_left, bg_top, bg_left + tw, bg_top + th))
    # 高斯模糊
    bg_blurred = bg_cropped.filter(ImageFilter.GaussianBlur(radius=35))
    # 降低微量亮度，凸显前景主体
    enhancer = ImageEnhance.Brightness(bg_blurred.convert("RGB"))
    canvas = enhancer.enhance(0.80).convert("RGBA")

    # 2. 前景主体：等比内嵌缩放
    fg_scale = min(tw / orig_w, th / orig_h)
    fg_w = int(orig_w * fg_scale)
    fg_h = int(orig_h * fg_scale)
    fg_resized = img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)

    # 3. 居中粘贴
    offset_x = (tw - fg_w) // 2
    offset_y = (th - fg_h) // 2

    canvas.paste(fg_resized, (offset_x, offset_y), fg_resized)
    return canvas


def enhance_portrait_beauty(
    image: Image.Image,
    smooth_level: float = 0.65,    # 磨皮强度 [0.0, 1.0]
    whiten_level: float = 0.35,    # 美白提亮 [0.0, 1.0]
    clarity_level: float = 0.50,   # 清晰锐化 [0.0, 1.0]
    rosy_level: float = 0.20       # 气色红润 [0.0, 1.0]
) -> Image.Image:
    """
    工业级人像超清美颜算法：
    1. 肤色智能分割定位（YCbCr + RGB 融合软蒙版，自动识别面部与人体皮肤区域）
    2. 保边磨皮（双边/表面模糊算法，抚平粗糙毛孔与噪点，完全保留眼睛、睫毛、鼻梁、唇线、发丝锐度）
    3. 肤色提亮美白与气色微调（提亮面部暗沉，剔除偏暗发黄泛青，恢复红润白皙质感）
    4. 细节超清与五官高光增强（USM 锐化五官轮廓，增强眼神光，画面立体通透）
    """
    try:
        import numpy as np

        orig_rgba = image.convert("RGBA")
        rgb = np.array(image.convert("RGB"), dtype=np.float32)

        # 1. 肤色软蒙版计算 (Skin Mask in YCbCr & RGB)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        cb = -0.168736 * r - 0.331264 * g + 0.5 * b + 128.0
        cr = 0.5 * r - 0.418688 * g - 0.081312 * b + 128.0

        # 高置信度肤色椭圆分布模型
        d_cb = (cb - 102.0) / 18.0
        d_cr = (cr - 146.0) / 18.0
        skin_dist = d_cb * d_cb + d_cr * d_cr
        skin_prob = np.clip(1.0 - skin_dist / 2.5, 0.0, 1.0)

        # RGB 启发式过滤（排除纯红背景与高光反射）
        rgb_rule = (r > g) & (g > b) & ((r - g) > 8.0) & (r > 60.0) & (b < 200.0)
        skin_mask = skin_prob * rgb_rule.astype(np.float32)

        mask_img = Image.fromarray((skin_mask * 255.0).astype(np.uint8), mode="L")
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=5))
        skin_weights = np.array(mask_img, dtype=np.float32) / 255.0
        skin_weights_3d = skin_weights[:, :, np.newaxis]

        # 2. 保边磨皮（Edge-Preserving Surface Smoothing）
        blur_img = image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=8))
        blur_rgb = np.array(blur_img, dtype=np.float32)

        diff = np.abs(rgb - blur_rgb)
        diff_max = np.max(diff, axis=2, keepdims=True)

        sigma_edge = 24.0
        edge_weight = np.exp(- (diff_max * diff_max) / (2.0 * sigma_edge * sigma_edge))

        smoothed_rgb = rgb * (1.0 - edge_weight) + blur_rgb * edge_weight
        effective_smooth = smooth_level * skin_weights_3d
        skin_smoothed_rgb = rgb * (1.0 - effective_smooth) + smoothed_rgb * effective_smooth

        # 3. 肤色提亮美白与气色红润（Skin Tone Brightening & Radiance）
        if whiten_level > 0.01:
            norm_val = skin_smoothed_rgb / 255.0
            gamma = 1.0 - (whiten_level * 0.22)
            brightened = np.power(np.clip(norm_val, 1e-4, 1.0), gamma) * 255.0

            if rosy_level > 0.01:
                brightened[:, :, 0] = brightened[:, :, 0] * (1.0 + rosy_level * 0.04)
                brightened[:, :, 2] = brightened[:, :, 2] * (1.0 + rosy_level * 0.03)

            skin_smoothed_rgb = skin_smoothed_rgb * (1.0 - skin_weights_3d) + brightened * skin_weights_3d

        skin_smoothed_rgb = np.clip(skin_smoothed_rgb, 0, 255).astype(np.uint8)
        enhanced_img = Image.fromarray(skin_smoothed_rgb, mode="RGB")

        # 4. 人物超清与五官轮廓锐化（Portrait Clarity & Detail Sharpening）
        if clarity_level > 0.01:
            usm_percent = int(80 + clarity_level * 100)
            enhanced_img = enhanced_img.filter(ImageFilter.UnsharpMask(radius=2, percent=usm_percent, threshold=3))
            contrast_boost = 1.0 + clarity_level * 0.06
            enhanced_img = ImageEnhance.Contrast(enhanced_img).enhance(contrast_boost)

        if orig_rgba.mode == "RGBA":
            enhanced_rgba = enhanced_img.convert("RGBA")
            enhanced_rgba.putalpha(orig_rgba.split()[3])
            return enhanced_rgba

        return enhanced_img
    except Exception as e:
        logger.warning("人像美颜与超清处理异常，安全回退原图: %s", e)
        return image


def _wrap_text_to_lines(text: str, max_chars_per_line: int = 8) -> List[str]:
    """对过长标题进行智能折行（针对短视频大字，单行一般不超过 8~10 个汉字）"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars_per_line:
        return [text]
    # 优先按标点、空格切分
    for sep in ["！", "!", "？", "?", "，", ",", " "]:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[:2]
    # 均匀对半切两行
    mid = (len(text) + 1) // 2
    return [text[:mid], text[mid:]]


# ---------------------------------------------------------------------------
# 视觉算法层：调色盘解析 / 双层描边 / 拱形弧排 / 羽化雾化 / 旋转贴纸
# ---------------------------------------------------------------------------
def _hex_to_rgba(color: Union[str, Tuple[int, ...]], alpha: int = 255) -> Tuple[int, int, int, int]:
    if isinstance(color, tuple):
        if len(color) == 4:
            return color
        elif len(color) == 3:
            return (color[0], color[1], color[2], alpha)
    color = (str(color or "#FFFFFF")).lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    try:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except (ValueError, IndexError):
        r, g, b = 255, 255, 255
    return (r, g, b, alpha)


def resolve_palette(theme: str) -> Dict[str, str]:
    """把主题标识解析为统一三色结构（main/sub/accent），旧主题自动映射到新调色盘保证存量工程可渲染"""
    theme = _LEGACY_PALETTE_ALIASES.get(theme, theme)
    if theme in COVER_PALETTES:
        return COVER_PALETTES[theme]
    if theme in _LEGACY_COLOR_MAP:
        legacy = _LEGACY_COLOR_MAP[theme]
        return {"main": legacy["primary"], "sub": legacy["badge_fg"], "accent": legacy["badge_bg"]}
    return COVER_PALETTES["classic_blue"]


def _legacy_palette(theme: str, default_key: str = "yellow_black") -> Dict[str, str]:
    """旧模板分支使用的旧结构调色盘（primary/secondary/badge_bg/badge_fg）"""
    if theme in _LEGACY_COLOR_MAP:
        return _LEGACY_COLOR_MAP[theme]
    pal = resolve_palette(theme)
    return {"primary": pal["main"], "secondary": pal["sub"], "badge_bg": pal["accent"], "badge_fg": pal["sub"]}


def _draw_double_stroke_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    core_fill: Tuple[int, int, int, int] | str,
    outer_width: int = 16,
    inner_width: int = 8,
    outer_fill: Tuple[int, int, int, int] | str = (255, 255, 255, 255),
    inner_fill: Tuple[int, int, int, int] | str = (0, 0, 0, 255)
) -> None:
    """双层描边贴纸大字：Painter's Algorithm 倒序三层渲染（外白厚边 → 内黑边 → 字芯原色）"""
    draw.text(xy, text, font=font, fill=core_fill, stroke_width=outer_width, stroke_fill=outer_fill)
    draw.text(xy, text, font=font, fill=core_fill, stroke_width=inner_width, stroke_fill=inner_fill)
    draw.text(xy, text, font=font, fill=core_fill)


def _build_fog_mask(
    size: Tuple[int, int],
    top_ratio: float = 0.45,
    max_alpha: int = 235
) -> Image.Image:
    """底部羽化白光 Alpha 蒙版：自 bottom 的 max_alpha 线性衰减至 top_ratio 处归零"""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    m_draw = ImageDraw.Draw(mask)
    start_y = int(h * top_ratio)
    span = max(1, h - start_y)
    for y in range(start_y, h):
        alpha = int(max_alpha * ((y - start_y) / span))
        m_draw.line([(0, y), (w, y)], fill=min(max_alpha, alpha))
    return mask


def _apply_fog_vignette(
    canvas: Image.Image,
    top_ratio: float = 0.45,
    max_alpha: int = 235
) -> Image.Image:
    """在画布下半部叠加柔和白色羽化雾化层，弱化杂乱实景背景"""
    w, h = canvas.size
    fog = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    fog.putalpha(_build_fog_mask((w, h), top_ratio=top_ratio, max_alpha=max_alpha))
    return Image.alpha_composite(canvas, fog)


def _arc_char_positions(
    text: str,
    center: Tuple[int, int],
    radius: int,
    per_char_angle: float = 11.0
) -> List[Tuple[float, float, float]]:
    """向上拱形弧排：逐字计算极坐标与切线旋转角，返回 [(x, y, 顺时针旋转角)]，左右对称环抱发顶"""
    n = max(1, len(text))
    total = per_char_angle * (n - 1)
    positions: List[Tuple[float, float, float]] = []
    cx, cy = center
    for i in range(n):
        theta = math.radians(-total / 2 + per_char_angle * i)  # 左负右正
        x = cx + radius * math.sin(theta)
        y = cy - radius * math.cos(theta)
        positions.append((x, y, -math.degrees(theta)))  # PIL 旋转逆时针为正，拱形字需顺时针倾斜
    return positions


def _draw_arc_text(
    canvas: Image.Image,
    text: str,
    center: Tuple[int, int],
    radius: int,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int, int] | str,
    stroke_width: int = 6,
    stroke_fill: Tuple[int, int, int, int] | str = (0, 0, 0, 255),
    per_char_angle: float = 11.0
) -> None:
    """在画布上绘制向上拱形弧排大字（逐字贴片旋转，避开人物面部环抱头顶）"""
    for ch, (x, y, rot) in zip(text, _arc_char_positions(text, center, radius, per_char_angle)):
        char_tile = Image.new("RGBA", (font.size * 3, font.size * 3), (0, 0, 0, 0))
        c_draw = ImageDraw.Draw(char_tile)
        c_draw.text(
            (font.size * 1.5, font.size * 1.5), ch, font=font, fill=fill,
            anchor="mm", stroke_width=stroke_width, stroke_fill=stroke_fill
        )
        rotated = char_tile.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
        canvas.paste(rotated, (int(x - rotated.width / 2), int(y - rotated.height / 2)), rotated)


def _make_text_tile(
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int, int] | str,
    stroke_width: int = 0,
    stroke_fill: Tuple[int, int, int, int] | str = (0, 0, 0, 255),
    bg_fill: Tuple[int, int, int, int] | None = None,
    pad_x: int = 0,
    pad_y: int = 0,
    radius: int = 0
) -> Image.Image:
    """把一行文字渲染为独立透明贴片（可整体旋转粘贴，用于倾角贴纸/倾斜副标）"""
    probe = Image.new("RGBA", (8, 8))
    p_draw = ImageDraw.Draw(probe)
    bbox = p_draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0] + pad_x * 2
    th = bbox[3] - bbox[1] + pad_y * 2
    tile = Image.new("RGBA", (max(4, tw), max(4, th)), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(tile)
    if bg_fill is not None:
        t_draw.rounded_rectangle([0, 0, tile.width - 1, tile.height - 1], radius=radius, fill=bg_fill)
    t_draw.text(
        (pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_fill
    )
    return tile


def _paste_rotated(canvas: Image.Image, tile: Image.Image, center: Tuple[int, int], angle: float) -> None:
    """把透明贴片绕中心旋转后粘贴到画布（角度为顺时针度数，模拟 -10° 动感倾角）"""
    rotated = tile.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True)
    px = int(center[0] - rotated.width / 2)
    py = int(center[1] - rotated.height / 2)
    canvas.paste(rotated, (px, py), rotated)


def _fit_font_size(text: str, base_size: int, max_chars: int) -> int:
    """字数超限时等比缩小字号，保证大字不溢出画布"""
    if len(text) <= max_chars:
        return base_size
    return max(48, int(base_size * max_chars / len(text)))


def _to_odd(x: Union[int, float]) -> int:
    """确保尺寸为奇数以满足 PIL MaxFilter 约束"""
    v = int(x)
    return v if v % 2 == 1 else v + 1


def _make_tight_char_sticker(
    ch: str,
    font: Any,
    angle: float = 0.0,
    core_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_color: Tuple[int, int, int, int] = (18, 80, 218, 255),
    outer_color: Optional[Tuple[int, int, int, int]] = None,
    v_scale: float = 1.14,
    core_expand: int = 6,
    stroke_w: int = 24,
    outer_w: int = 0,
) -> Image.Image:
    """制作单字独立贴纸：字芯 + 饱满描边 + 柔和阴影（默认去掉外圈白边），精确裁剪外透明边框"""
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), ch, font=font)
    cw, ch_h = max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])
    pad = 40
    w, h = int(cw + pad * 2), int(ch_h + pad * 2)

    raw_m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(raw_m)
    d.text((pad - bbox[0], pad - bbox[1]), ch, font=font, fill=255)

    if v_scale != 1.0:
        new_h = max(1, int(h * v_scale))
        raw_m = raw_m.resize((w, new_h), Image.Resampling.BICUBIC)
        h = new_h

    core_m = raw_m.filter(ImageFilter.MaxFilter(_to_odd(core_expand)))
    stroke_m = core_m.filter(ImageFilter.MaxFilter(_to_odd(stroke_w)))

    stk = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if outer_w > 0 and outer_color:
        outer_m = stroke_m.filter(ImageFilter.MaxFilter(_to_odd(outer_w)))
        stk.paste(Image.new("RGBA", (w, h), outer_color), (0, 0), outer_m)
    stk.paste(Image.new("RGBA", (w, h), stroke_color), (0, 0), stroke_m)
    stk.paste(Image.new("RGBA", (w, h), core_color), (0, 0), core_m)

    if angle != 0:
        stk = stk.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)

    rot_a = stk.split()[3]
    s_mask = rot_a.filter(ImageFilter.GaussianBlur(6))
    sw, sh = stk.size
    final_stk = Image.new("RGBA", (sw + 14, sh + 14), (0, 0, 0, 0))
    final_stk.paste(Image.new("RGBA", (sw, sh), (0, 0, 0, 85)), (3, 5), s_mask)
    final_stk.paste(stk, (0, 0), stk)

    bbox_crop = final_stk.getbbox()
    if bbox_crop:
        final_stk = final_stk.crop(bbox_crop)
    return final_stk


def _make_unified_row_sticker(
    text: str,
    font: Any,
    angle: float = 0.0,
    core_color: Tuple[int, int, int, int] = (255, 238, 10, 255),
    stroke_color: Tuple[int, int, int, int] = (18, 80, 218, 255),
    letter_spacing: int = -5,
    stroke_w: int = 26,
    core_expand: int = 6,
    fill_gaps: bool = True
) -> Image.Image:
    """整行文本连体贴纸：字间描边闭合融合，消除字间孤立漏光三角缝隙"""
    chars = list(text)
    if not chars:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bboxes = [dummy.textbbox((0, 0), ch, font=font) for ch in chars]
    widths = [max(1, b[2] - b[0]) for b in bboxes]
    max_h = max(max(1, b[3] - b[1]) for b in bboxes)

    total_w = sum(widths) + letter_spacing * (len(chars) - 1)
    pad = 60
    w = int(total_w + pad * 2)
    h = int(max_h * 1.15 + pad * 2)

    raw_m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(raw_m)
    cur_x = pad
    baseline = pad + int(max_h * 0.9)
    for ch, b, cw in zip(chars, bboxes, widths):
        d.text((cur_x - b[0], baseline - b[3]), ch, font=font, fill=255)
        cur_x += cw + letter_spacing

    h_new = max(1, int(h * 1.12))
    raw_m = raw_m.resize((w, h_new), Image.Resampling.BICUBIC)
    h = h_new

    core_m = raw_m.filter(ImageFilter.MaxFilter(_to_odd(core_expand)))
    stroke_m = core_m.filter(ImageFilter.MaxFilter(_to_odd(stroke_w)))

    if fill_gaps:
        stroke_m = stroke_m.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.MinFilter(11))

    stk = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    stk.paste(Image.new("RGBA", (w, h), stroke_color), (0, 0), stroke_m)
    stk.paste(Image.new("RGBA", (w, h), core_color), (0, 0), core_m)

    if angle != 0:
        stk = stk.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC)

    rot_a = stk.split()[3]
    s_mask = rot_a.filter(ImageFilter.GaussianBlur(2))
    sw, sh = stk.size
    final_stk = Image.new("RGBA", (sw + 8, sh + 8), (0, 0, 0, 0))
    final_stk.paste(Image.new("RGBA", (sw, sh), (0, 0, 0, 60)), (2, 3), s_mask)
    final_stk.paste(stk, (0, 0), stk)

    bbox_crop = final_stk.getbbox()
    if bbox_crop:
        final_stk = final_stk.crop(bbox_crop)
    return final_stk


def _make_unified_arc_banner(
    text: str,
    font: Any,
    core_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_color: Tuple[int, int, int, int] = (18, 80, 218, 255),
    stroke_w: int = 26,
    core_expand: int = 6
) -> Image.Image:
    """顶部拱形整体彩虹大字：拱桥弧度排列，字间描边一体闭合，零漏光缝隙"""
    chars = list(text)
    n = len(chars)
    if n == 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bboxes = [dummy.textbbox((0, 0), ch, font=font) for ch in chars]
    widths = [max(1, b[2] - b[0]) for b in bboxes]

    letter_gap = -10
    total_w = sum(widths) + letter_gap * (n - 1)

    pad = 80
    w = int(total_w + pad * 2)
    font_size = getattr(font, "size", 188)
    h = int(font_size * 2.2 + pad * 2)

    raw_m = Image.new("L", (w, h), 0)
    max_deg = 7.0
    angles = [-max_deg + (2 * max_deg * i / (n - 1)) for i in range(n)] if n > 1 else [0.0]
    cur_x = pad
    peak_y = pad + 60

    for ch, b, cw, ang in zip(chars, bboxes, widths, angles):
        ch_w = max(1, b[2] - b[0] + 40)
        ch_h = max(1, b[3] - b[1] + 40)
        ch_img = Image.new("L", (ch_w, ch_h), 0)
        ch_d = ImageDraw.Draw(ch_img)
        ch_d.text((20 - b[0], 20 - b[1]), ch, font=font, fill=255)
        rot_ch = ch_img.rotate(-ang, expand=True, resample=Image.Resampling.BICUBIC)

        dx = (cur_x + cw // 2) - (pad + total_w // 2)
        y_pos = int(peak_y + 0.00035 * (dx ** 2))

        raw_m.paste(rot_ch, (cur_x - 20, y_pos - 20), rot_ch)
        cur_x += cw + letter_gap

    h_new = max(1, int(h * 1.12))
    raw_m = raw_m.resize((w, h_new), Image.Resampling.BICUBIC)
    h = h_new

    core_m = raw_m.filter(ImageFilter.MaxFilter(_to_odd(core_expand)))
    stroke_m = core_m.filter(ImageFilter.MaxFilter(_to_odd(stroke_w)))
    stroke_m = stroke_m.filter(ImageFilter.MaxFilter(11)).filter(ImageFilter.MinFilter(11))

    stk = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    stk.paste(Image.new("RGBA", (w, h), stroke_color), (0, 0), stroke_m)
    stk.paste(Image.new("RGBA", (w, h), core_color), (0, 0), core_m)

    rot_a = stk.split()[3]
    s_mask = rot_a.filter(ImageFilter.GaussianBlur(2))
    sw, sh = stk.size
    final_stk = Image.new("RGBA", (sw + 8, sh + 8), (0, 0, 0, 0))
    final_stk.paste(Image.new("RGBA", (sw, sh), (0, 0, 0, 60)), (2, 3), s_mask)
    final_stk.paste(stk, (0, 0), stk)

    bbox_crop = final_stk.getbbox()
    if bbox_crop:
        final_stk = final_stk.crop(bbox_crop)
    return final_stk


# ---------------------------------------------------------------------------
# R3 分区文本样式覆盖（location | main | sub）：渲染取色三级优先级
# 分区覆盖 → 模板默认 → 调色盘；scale/offset_y 双向 clamp；前端 Canvas 同规则镜像
# ---------------------------------------------------------------------------
def _resolve_zone_styles(config: CoverDesignConfig, canvas_h: int) -> Dict[str, Dict[str, Any]]:
    """解析三分区覆盖样式为渲染参数（违法颜色/键已在实体层 422，此处再防御性兜底）"""
    styles: Dict[str, Dict[str, Any]] = {
        zone: {"scale": 1.0, "off_x": 0, "off_y": 0, "text": None, "stroke": None}
        for zone in ("location", "main", "sub")
    }
    raw_zone_styles = getattr(config, "zone_styles", None)
    if isinstance(raw_zone_styles, dict):
        items = raw_zone_styles.items()
    else:
        items = []

    canvas_w = int(canvas_h * 9 / 16)
    for key, zs in items:
        if key not in styles or zs is None:
            continue
        entry = styles[key]

        def _get_val(obj: Any, name: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)

        try:
            entry["scale"] = min(1.4, max(0.6, float(_get_val(zs, "scale", 1.0) or 1.0)))
        except (TypeError, ValueError):
            pass
        try:
            entry["off_x"] = int(canvas_w * min(0.20, max(-0.20, float(_get_val(zs, "offset_x", 0.0) or 0.0))))
        except (TypeError, ValueError):
            pass
        try:
            entry["off_y"] = int(canvas_h * min(0.12, max(-0.12, float(_get_val(zs, "offset_y", 0.0) or 0.0))))
        except (TypeError, ValueError):
            pass
        for field, attr in (("text_color", "text"), ("stroke_color", "stroke")):
            raw = str(_get_val(zs, field, "") or "").strip()
            if re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
                entry[attr] = raw
    return styles


def _clamp_element_y(y: float, canvas_h: int, margin_ratio: float = 0.03) -> int:
    """纵向偏移后的位置钳制：元素锚点永不越出画布（与前端同规则，margin 3% 画布高）"""
    top = int(canvas_h * margin_ratio)
    bottom = int(canvas_h * (1 - margin_ratio))
    return int(min(max(y, top), bottom))


def _clamp_y_in_band(y: float, band_top: float, band_bottom: float, text_h: float, pad: float) -> int:
    """色带内文字的纵向钳制：整行文字（含偏移）永不滑出色带与同色底融合（与前端同规则）"""
    top = band_top + pad
    bottom = band_bottom - text_h - pad
    if bottom < top:
        return int((band_top + band_bottom) / 2 - text_h / 2)
    return int(min(max(y, top), bottom))


def _zone_scaled(base_size: int, zone: Dict[str, Any]) -> int:
    """字号 = 基准 × 分区 scale（clamp [0.6,1.4] 后取整，下限 24 保证可读）"""
    return max(24, int(base_size * zone["scale"]))


def render_cover_image(
    base_image: Image.Image,
    config: CoverDesignConfig,
    target_size: Tuple[int, int] = (TARGET_WIDTH, TARGET_HEIGHT)
) -> Image.Image:
    """
    基于底图和封面配置，渲染出标准 1080x1920 印刷级高清封面。

    6 大实战模板以 location_tag（地域词）为第一视觉锚点；
    旧 4 模板（gold_bold/color_badge/dual_contrast）保留渲染兼容。
    """
    tw, th = target_size
    # 1. 画幅自适应
    canvas = adapt_image_aspect_ratio(base_image, target_size=target_size, mode=config.aspect_mode)

    # 1.5 人像超清与美颜增强处理（智能识别肤色 + 保边磨皮 + 轮廓五官微锐化 + 气色提亮）
    if getattr(config, "enable_portrait_enhancement", True):
        mode = getattr(config, "beauty_mode", "natural")
        if mode != "off":
            b_strength = float(getattr(config, "beauty_strength", 0.70) or 0.70)
            c_strength = float(getattr(config, "clarity_strength", 0.50) or 0.50)
            if mode == "hd_clear":
                canvas = enhance_portrait_beauty(canvas, smooth_level=b_strength * 0.5, whiten_level=0.25, clarity_level=c_strength * 1.3, rosy_level=0.15)
            elif mode == "delicate":
                canvas = enhance_portrait_beauty(canvas, smooth_level=b_strength * 1.15, whiten_level=0.45, clarity_level=c_strength * 0.9, rosy_level=0.35)
            else:  # "natural"
                canvas = enhance_portrait_beauty(canvas, smooth_level=b_strength, whiten_level=0.35, clarity_level=c_strength, rosy_level=0.22)

    location_tag = (config.location_tag or "").strip()
    main_text = (config.main_title or "").strip()
    sub_text = (config.sub_title or "").strip()
    template_id = (config.template_id or "sticker_double_stroke").strip()
    theme = (config.color_theme or "classic_blue").strip()
    family = (config.font_family or "heavy_gothic").strip()

    # 未填任何文案时的规则兜底（保证模板渲染永不为空白纯图）
    anchor_text = location_tag or main_text or "同城学车不踩坑"

    pal = resolve_palette(theme)
    zones = _resolve_zone_styles(config, th)
    z_loc, z_main, z_sub = zones["location"], zones["main"], zones["sub"]

    # 2. 依据模板排版绘制
    if template_id in ("pure_image", "none", "original", "clean"):
        # 纯净原图直出模式：不叠加任何文字、贴纸或遮罩，直接输出高画质自适应底图
        return canvas.convert("RGB")

    if template_id == "sticker_double_stroke":
        # 双标题贴纸风（真实爆款账号同款）：顶部地域大字（彩色字芯+超粗纯白描边+柔和投影，
        # 位于画面上部 ≤22% 不挡人脸）+ 下方钩子大字（行楷手写体，胸前 60%~78%，避开平台底部 UI）
        draw = ImageDraw.Draw(canvas)
        tag_lines = _wrap_text_to_lines(anchor_text, max_chars_per_line=6)
        tag_font = get_font(_zone_scaled(_fit_font_size(anchor_text, 168, 6), z_loc), bold=True, family=family)
        curr_y = _clamp_element_y(int(th * 0.085) + z_loc["off_y"], th)
        for line in tag_lines:
            bbox = draw.textbbox((0, 0), line, font=tag_font, stroke_width=18)
            lx = (tw - (bbox[2] - bbox[0])) // 2 - bbox[0]
            # 柔和投影 → 超粗纯白描边 → 彩色字芯（分区可覆盖字芯/描边色）
            draw.text((lx + 9, curr_y + 12), line, font=tag_font, fill=(0, 0, 0, 80), stroke_width=18, stroke_fill=(0, 0, 0, 80))
            draw.text((lx, curr_y), line, font=tag_font, fill=_hex_to_rgba(z_loc["text"] or pal["main"]), stroke_width=18, stroke_fill=_hex_to_rgba(z_loc["stroke"] or "#FFFFFF"))
            curr_y = _clamp_element_y(curr_y + (bbox[3] - bbox[1]) + 26, th)

        hook_text = main_text if (location_tag and main_text) else (main_text or sub_text)
        tail_text = sub_text if (location_tag and main_text and sub_text) else ""
        if hook_text:
            hook_font = get_font(_zone_scaled(_fit_font_size(hook_text, 116, 8), z_main), bold=True, family="handwriting_tilt")
            hook_lines = _wrap_text_to_lines(hook_text, max_chars_per_line=8)
            hook_tile = _make_text_tile(
                "\n".join(hook_lines), hook_font,
                fill=_hex_to_rgba(z_main["text"] or "#FFFFFF"), stroke_width=10, stroke_fill=_hex_to_rgba(z_main["stroke"] or pal["main"]),
                pad_x=20, pad_y=14
            )
            _paste_rotated(canvas, hook_tile, (tw // 2, _clamp_element_y(int(th * 0.655) + z_main["off_y"], th)), angle=-3)

        if tail_text:
            cap_font = get_font(_zone_scaled(_fit_font_size(tail_text, 54, 10), z_sub), bold=True, family="handwriting_tilt")
            cap_tile = _make_text_tile(
                tail_text, cap_font,
                fill=_hex_to_rgba(z_sub["text"] or pal["accent"]), stroke_width=6, stroke_fill=_hex_to_rgba(z_sub["stroke"] or "#FFFFFF"),
                pad_x=10, pad_y=8
            )
            _paste_rotated(canvas, cap_tile, (tw // 2, _clamp_element_y(int(th * 0.775) + z_sub["off_y"], th)), angle=-3)

    elif template_id == "split_contrast_bar":
        # 上下通栏权威撞色条：顶部全宽通栏（书法白字）+ 底部白通栏（深红痛点大字，上移避开平台底部 UI）
        draw = ImageDraw.Draw(canvas)
        top_h = int(th * 0.16)
        draw.rectangle([0, 0, tw, top_h], fill=_hex_to_rgba(pal["main"]))
        tag_text = anchor_text
        t_font = get_font(_zone_scaled(_fit_font_size(tag_text, 118, 6), z_loc), bold=True, family=family)
        tb = draw.textbbox((0, 0), tag_text, font=t_font)
        draw.text(
            ((tw - (tb[2] - tb[0])) // 2 - tb[0], _clamp_element_y((top_h - (tb[3] - tb[1])) // 2 - tb[1] + z_loc["off_y"], th)),
            tag_text, font=t_font, fill=_hex_to_rgba(z_loc["text"] or pal["sub"])
        )

        bot_h = int(th * 0.17)
        bot_y = int(th * 0.73)
        bot_bottom = min(th, bot_y + bot_h)
        draw.rectangle([0, bot_y, tw, bot_bottom], fill=(255, 255, 255, 255))
        body_font = get_font(_zone_scaled(_fit_font_size(main_text or tag_text, 96, 7), z_main), bold=True, family=family)
        body_lines = _wrap_text_to_lines(main_text or tag_text, max_chars_per_line=7)
        body_bboxes = [draw.textbbox((0, 0), l, font=body_font) for l in body_lines]
        s_font = get_font(_zone_scaled(40, z_sub), bold=False, family=family)
        has_sub = bool(sub_text)
        sb = draw.textbbox((0, 0), sub_text, font=s_font) if has_sub else None
        gap = 18
        # 主文案+副标作为整块布局：块起点一次性钳入白色通栏，块内行距固定，杜绝偏移后行间互压
        block_h = sum(b[3] - b[1] for b in body_bboxes) + gap * max(0, len(body_lines) - 1)
        if has_sub and sb is not None:
            block_h += 8 + (sb[3] - sb[1])
        pad = th * 0.008
        by = min(max(bot_y + int(bot_h * 0.16) + z_main["off_y"], bot_y + pad), max(bot_y + pad, bot_bottom - block_h - pad))
        for line, lb in zip(body_lines, body_bboxes):
            # 通栏大字默认无描边（深红字压白底）；用户显式覆盖描边色时补绘描边层，杜绝白字压白底隐形
            draw.text(((tw - (lb[2] - lb[0])) // 2 - lb[0], by - lb[1]), line, font=body_font,
                      fill=_hex_to_rgba(z_main["text"] or pal["main"]),
                      stroke_width=5 if z_main["stroke"] else 0,
                      stroke_fill=_hex_to_rgba(z_main["stroke"] or "#000000"))
            by += (lb[3] - lb[1]) + gap
        if has_sub and sb is not None:
            sy = by + 8 + z_sub["off_y"]
            sy = min(max(sy, bot_y + pad), bot_bottom - (sb[3] - sb[1]) - pad)
            draw.text(((tw - (sb[2] - sb[0])) // 2 - sb[0], sy - sb[1]), sub_text, font=s_font,
                      fill=_hex_to_rgba(z_sub["text"] or "#6B7280"),
                      stroke_width=2 if z_sub["stroke"] else 0,
                      stroke_fill=_hex_to_rgba(z_sub["stroke"] or "#FFFFFF"))

    elif template_id == "rainbow_arc_header":
        # 拱形包头彩虹字：弧顶抬升至约 17% 高度，字符沿弧线环抱头顶（17%~23%），绝不压 25% 以下的脸部区域
        arc_text = anchor_text
        a_font = get_font(_zone_scaled(_fit_font_size(arc_text, 118, 7), z_loc), bold=True, family=family)
        _draw_arc_text(
            canvas, arc_text,
            center=(tw // 2, _clamp_element_y(int(th * 0.43) + z_loc["off_y"], th)), radius=int(tw * 0.46),
            font=a_font, fill=_hex_to_rgba(z_loc["text"] or pal["main"]), stroke_width=6,
            stroke_fill=_hex_to_rgba(z_loc["stroke"] or "#000000"), per_char_angle=12.0
        )
        draw = ImageDraw.Draw(canvas)
        # 顶部右侧斜角账号/胶囊标
        badge_text = sub_text or "@同城学车"
        b_font = get_font(_zone_scaled(38, z_sub), bold=True, family=family)
        badge_tile = _make_text_tile(
            badge_text, b_font, fill=_hex_to_rgba(z_sub["text"] or "#FFFFFF"),
            stroke_width=2 if z_sub["stroke"] else 0,
            stroke_fill=_hex_to_rgba(z_sub["stroke"] or "#FFFFFF"),
            bg_fill=_hex_to_rgba(pal["main"]), pad_x=26, pad_y=14, radius=24
        )
        _paste_rotated(canvas, badge_tile, (int(tw * 0.80), _clamp_element_y(int(th * 0.115) + z_sub["off_y"], th)), angle=-8)
        # 底部手写疑问/感叹句（上移至 80%，避开抖音底部标题与互动区）
        q_text = main_text if location_tag else (main_text or sub_text)
        if q_text:
            q_font = get_font(_zone_scaled(_fit_font_size(q_text, 84, 8), z_main), bold=True, family=family)
            q_tile = _make_text_tile(
                q_text, q_font, fill=_hex_to_rgba(z_main["text"] or "#FFFFFF"),
                stroke_width=6, stroke_fill=_hex_to_rgba(z_main["stroke"] or "#000000"), pad_x=10, pad_y=8
            )
            _paste_rotated(canvas, q_tile, (tw // 2, _clamp_element_y(int(th * 0.80) + z_main["off_y"], th)), angle=-6)

    elif template_id == "bottom_fog_vignette":
        # 胸前羽化白光沉浸字：底部白色雾化遮罩 + 深红白边立体特大字 + 顶部倾斜副标
        # 无地域词时胸前大字即主标题钩子，分区归属随内容切换（data-model §1.1.1 映射表）
        canvas = _apply_fog_vignette(canvas, top_ratio=0.42, max_alpha=235)
        draw = ImageDraw.Draw(canvas)
        big_zone = z_loc if location_tag else z_main
        big_text = anchor_text
        g_font = get_font(_zone_scaled(_fit_font_size(big_text, 140, 6), big_zone), bold=True, family=family)
        gy = _clamp_element_y(int(th * 0.62) + big_zone["off_y"], th)
        for line in _wrap_text_to_lines(big_text, max_chars_per_line=6):
            lb = draw.textbbox((0, 0), line, font=g_font, stroke_width=12)
            lx = (tw - (lb[2] - lb[0])) // 2 - lb[0]
            draw.text((lx + 6, gy + 8), line, font=g_font, fill=(0, 0, 0, 90), stroke_width=12, stroke_fill=(0, 0, 0, 90))
            draw.text((lx, gy), line, font=g_font, fill=_hex_to_rgba(big_zone["text"] or pal["main"]), stroke_width=12, stroke_fill=_hex_to_rgba(big_zone["stroke"] or "#FFFFFF"))
            gy = _clamp_element_y(gy + (lb[3] - lb[1]) + 26, th)
        # 有地域词时胸前大字为地域锚点，主标题钩子另起一行（雾化区 80%），保证 main 分区在 fog 模板亦有元素
        if location_tag and main_text:
            hook_font = get_font(_zone_scaled(_fit_font_size(main_text, 72, 8), z_main), bold=True, family="handwriting_tilt")
            hook_tile = _make_text_tile(
                main_text, hook_font, fill=_hex_to_rgba(z_main["text"] or "#FFFFFF"),
                stroke_width=6, stroke_fill=_hex_to_rgba(z_main["stroke"] or "#000000"), pad_x=10, pad_y=8
            )
            _paste_rotated(canvas, hook_tile, (tw // 2, _clamp_element_y(int(th * 0.80) + z_main["off_y"], th)), angle=-4)
        if sub_text:
            s_font = get_font(_zone_scaled(_fit_font_size(sub_text, 52, 10), z_sub), bold=True, family=family)
            s_tile = _make_text_tile(
                sub_text, s_font, fill=_hex_to_rgba(z_sub["text"] or pal["accent"]),
                stroke_width=4, stroke_fill=_hex_to_rgba(z_sub["stroke"] or "#FFFFFF"), pad_x=8, pad_y=6
            )
            _paste_rotated(canvas, s_tile, (int(tw * 0.30), _clamp_element_y(int(th * 0.13) + z_sub["off_y"], th)), angle=-6)

    elif template_id == "angled_impact_stamp":
        # 倾角冲击引流标：-10° 地域贴纸 + 右侧双行金色口诀 + 底部警示通栏
        draw = ImageDraw.Draw(canvas)
        stamp_text = anchor_text
        st_font = get_font(_zone_scaled(_fit_font_size(stamp_text, 112, 6), z_loc), bold=True, family=family)
        stamp_tile = _make_text_tile(
            stamp_text, st_font, fill=_hex_to_rgba(z_loc["text"] or "#FFFFFF"),
            stroke_width=5, stroke_fill=_hex_to_rgba(z_loc["stroke"] or "#000000"),
            bg_fill=_hex_to_rgba(pal["main"]), pad_x=38, pad_y=24, radius=18
        )
        _paste_rotated(canvas, stamp_tile, (int(tw * 0.40), _clamp_element_y(int(th * 0.16) + z_loc["off_y"], th)), angle=-10)

        right_text = main_text if location_tag else (main_text or sub_text)
        if right_text:
            r_font = get_font(_zone_scaled(76, z_main), bold=True, family=family)
            ry = _clamp_element_y(int(th * 0.34) + z_main["off_y"], th)
            for line in _wrap_text_to_lines(right_text, max_chars_per_line=4)[:2]:
                lb = draw.textbbox((0, 0), line, font=r_font, stroke_width=5)
                rx = int(tw * 0.94) - (lb[2] - lb[0])
                draw.text((rx, ry), line, font=r_font, fill=_hex_to_rgba(z_main["text"] or pal["sub"]), stroke_width=5, stroke_fill=_hex_to_rgba(z_main["stroke"] or "#000000"))
                ry = _clamp_element_y(ry + (lb[3] - lb[1]) + 16, th)

        ban_h = int(th * 0.085)
        ban_y = int(th * 0.745)
        draw.rectangle([0, ban_y, tw, ban_y + ban_h], fill=_hex_to_rgba(pal["accent"]))
        warn_text = sub_text or "评论区咨询"
        w_font = get_font(_zone_scaled(_fit_font_size(warn_text, 46, 12), z_sub), bold=True, family=family)
        wb = draw.textbbox((0, 0), warn_text, font=w_font)
        wy = _clamp_y_in_band(
            ban_y + (ban_h - (wb[3] - wb[1])) // 2 - wb[1] + z_sub["off_y"],
            ban_y, ban_y + ban_h, wb[3] - wb[1], pad=th * 0.006
        )
        draw.text(
            ((tw - (wb[2] - wb[0])) // 2 - wb[0], wy),
            warn_text, font=w_font,
            fill=_hex_to_rgba(z_sub["text"] or "#FFFFFF"),
            stroke_width=3 if z_sub["stroke"] else 0,
            stroke_fill=_hex_to_rgba(z_sub["stroke"] or "#000000")
        )

    elif template_id == "clean_editorial":
        # 极简轻奢杂志风：顶部英文章节标 + 地域衬线行 + 居中纯白大字 + 细横线 + 衬线副标
        # 有地域词时大字即主标题钩子（main 区），无地域词时大字承担地域锚点（location 区）；
        # 地域行独立渲染，保证 location 分区在本模板亦有元素
        draw = ImageDraw.Draw(canvas)
        label_font = get_font(30, bold=False, family="editorial_serif")
        label = "F E A T U R E D  S T O R Y"
        lb = draw.textbbox((0, 0), label, font=label_font)
        label_x = (tw - (lb[2] - lb[0])) // 2
        label_y = int(th * 0.10)
        # 柔和暗影垫底，防止浅色实景（天空/太阳）吃掉白色小字
        draw.text((label_x + 2, label_y + 2), label, font=label_font, fill=(15, 23, 42, 130))
        draw.text((label_x, label_y), label, font=label_font, fill=(255, 255, 255, 245))

        if location_tag:
            loc_font = get_font(_zone_scaled(44, z_loc), bold=True, family="editorial_serif")
            lb2 = draw.textbbox((0, 0), location_tag, font=loc_font)
            lx2 = (tw - (lb2[2] - lb2[0])) // 2
            ly2 = _clamp_element_y(int(th * 0.465) + z_loc["off_y"], th)
            draw.text((lx2 + 2, ly2 + 2), location_tag, font=loc_font, fill=(15, 23, 42, 130))
            if z_loc["stroke"]:
                draw.text((lx2, ly2), location_tag, font=loc_font, fill=_hex_to_rgba(z_loc["text"] or pal["main"]), stroke_width=3, stroke_fill=_hex_to_rgba(z_loc["stroke"]))
            else:
                draw.text((lx2, ly2), location_tag, font=loc_font, fill=_hex_to_rgba(z_loc["text"] or pal["main"]))

        body_text = anchor_text if not location_tag else (main_text or anchor_text)
        body_zone = z_main if location_tag else z_loc
        m_font = get_font(_zone_scaled(_fit_font_size(body_text, 100, 8), body_zone), bold=True, family="editorial_serif")
        my = _clamp_element_y(int(th * 0.55) + body_zone["off_y"], th)
        for line in _wrap_text_to_lines(body_text, max_chars_per_line=8):
            mb = draw.textbbox((0, 0), line, font=m_font)
            mx = (tw - (mb[2] - mb[0])) // 2
            draw.text((mx + 3, my + 3), line, font=m_font, fill=(0, 0, 0, 150))
            if body_zone["stroke"]:
                # 用户显式指定描边色时补绘描边层（默认无描边，保持杂志风留白）
                draw.text((mx, my), line, font=m_font, fill=_hex_to_rgba(body_zone["text"] or "#FFFFFF"), stroke_width=3, stroke_fill=_hex_to_rgba(body_zone["stroke"]))
            else:
                draw.text((mx, my), line, font=m_font, fill=_hex_to_rgba(body_zone["text"] or "#FFFFFF"))
            my = _clamp_element_y(my + (mb[3] - mb[1]) + 24, th)

        line_w = int(tw * 0.30)
        draw.rectangle([(tw - line_w) // 2, my + 18, (tw + line_w) // 2, my + 20], fill=(226, 232, 240, 220))

        if sub_text:
            s_font = get_font(_zone_scaled(42, z_sub), bold=False, family="editorial_serif")
            sb = draw.textbbox((0, 0), sub_text, font=s_font)
            draw.text(((tw - (sb[2] - sb[0])) // 2, _clamp_element_y(my + 44 + z_sub["off_y"], th)), sub_text, font=s_font, fill=_hex_to_rgba(z_sub["text"] or "#E2E8F0"))

    elif template_id in ("text_behind_person", "three_tier_burst"):
        # 同城爆款三段贴纸大字（兔牙教练同款）：
        # 1. 顶部地域大字：微弧抛物线拱形排列，单字独立贴纸（白字芯+宝蓝描边+纯白外边），微隙 8px 不黏连
        # 2. 胸前引导词：独立小标（白字芯+宝蓝内边+白外边），微隙 4px
        # 严格解耦三大区域，禁止跨区域混杂或长标题污染
        top_text = (location_tag or "").strip()
        sub_hook = (sub_text or "").strip()
        bot_hook = (main_text or "").strip()

        # 区域 1：顶部微弧拱桥（一体化闭合色带，零缝隙）
        top_chars = list(top_text)
        n_top = len(top_chars)
        if n_top > 0:
            if n_top <= 4:
                top_base = 205
            elif n_top == 5:
                top_base = 180
            elif n_top == 6:
                top_base = 160
            elif n_top <= 8:
                top_base = 142
            else:
                top_base = max(112, int(205 * 4 / n_top))
            top_base_size = _zone_scaled(top_base, z_loc)
            top_font = get_font(top_base_size, bold=True, family=family)
            top_core = _hex_to_rgba(z_loc["text"] or "#FFFFFF")
            top_stroke = _hex_to_rgba(z_loc["stroke"] or pal.get("main", "#124CD6"))

            top_stk = _make_unified_arc_banner(
                top_text, top_font,
                core_color=top_core, stroke_color=top_stroke,
                stroke_w=26, core_expand=6
            )
            top_x = (tw - top_stk.width) // 2 + z_loc["off_x"]
            top_y = _clamp_element_y(105 + z_loc["off_y"], th)
            canvas.paste(top_stk, (top_x, top_y), top_stk)

        # 区域 2：胸前引导小标（一体化连体，零缝隙）
        sub_chars = list(sub_hook)
        n_sub = len(sub_chars)
        if n_sub > 0:
            sub_base_size = _zone_scaled(94, z_sub)
            sub_font = get_font(sub_base_size, bold=True, family=family)
            sub_core = _hex_to_rgba(z_sub["text"] or "#FFFFFF")
            sub_stroke = _hex_to_rgba(z_sub["stroke"] or pal.get("main", "#124CD6"))
            sub_stk = _make_unified_row_sticker(
                sub_hook, sub_font, angle=-3.8,
                core_color=sub_core, stroke_color=sub_stroke,
                letter_spacing=-4, stroke_w=20, core_expand=5
            )
            sub_x = int(tw * 0.11) + z_sub["off_x"]
            sub_y = _clamp_element_y(int(th * 0.60) + z_sub["off_y"], th)
            canvas.paste(sub_stk, (sub_x, sub_y), sub_stk)

        # 区域 3：底部黄色大字（一体化连体贴纸，彻底填实所有字间三角缝隙！）
        bot_chars = list(bot_hook)
        n_bot = len(bot_chars)
        if n_bot > 0:
            bot_base = 142
            if n_bot >= 7:
                bot_base = 132
            elif n_bot == 6:
                bot_base = 140
            bot_size = _zone_scaled(bot_base, z_main)
            bot_font = get_font(bot_size, bold=True, family=family)
            bot_core = _hex_to_rgba(z_main["text"] or pal.get("accent", "#FFDD00"))
            bot_stroke = _hex_to_rgba(z_main["stroke"] or pal.get("main", "#124CD6"))
            bot_stk = _make_unified_row_sticker(
                bot_hook, bot_font, angle=-3.2,
                core_color=bot_core, stroke_color=bot_stroke,
                letter_spacing=-6, stroke_w=26, core_expand=6,
                fill_gaps=True
            )
            bot_x = (tw - bot_stk.width) // 2 + z_main["off_x"]
            bot_y = _clamp_element_y(int(th * 0.68) + z_main["off_y"], th)
            canvas.paste(bot_stk, (bot_x, bot_y), bot_stk)

    elif template_id == "neon_3d_sticker":
        # 荧光绿 3D 贴纸大字（同城爆款争议/干货教学款）：
        # 1. 顶部微弧 3D 实体下沉大字（荧光柠檬黄字芯 + 墨绿 3D 实体块面挤压厚度 + 极细硬边）
        # 2. 胸前引导小标（纯白字芯 + 墨绿 3D 实体下沉厚度）
        # 3. 底部转化大字（纯白字芯 + 墨绿 3D 实体下沉厚度）
        # 4. 手绘白色高光贴纸涂鸦（左上 △ △、面颊与底部 \ | / 强调线条）
        top_text = (location_tag or "").strip() or (main_text or "").strip()
        sub_hook = (sub_text or "").strip()
        bot_hook = (main_text if location_tag else "").strip()

        def _render_3d_text_block(
            target_canvas: Image.Image,
            text_str: str,
            center_pos: Tuple[int, int],
            font_size: int,
            front_c: Tuple[int, int, int, int],
            extrude_c: Tuple[int, int, int, int],
            depth_px: int = 24,
            angle_val: float = 0.0,
            arc_val: float = 0.0,
            stroke_width: int = 3,
            stroke_c: Tuple[int, int, int, int] = (24, 52, 1, 255)
        ):
            f = get_font(font_size, bold=True, family=family)
            chars = list(text_str)
            if not chars:
                return
            dummy_d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            bboxes = [dummy_d.textbbox((0, 0), ch, font=f) for ch in chars]
            widths = [max(1, b[2] - b[0]) for b in bboxes]
            total_w = sum(widths) + 2 * (len(chars) - 1)

            pad = 140 + depth_px
            layer_w = total_w + pad * 2
            layer_h = int(font_size * 2.2) + pad * 2

            layer = Image.new("RGBA", (layer_w, layer_h), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)

            cur_x = pad
            peak_y = pad + 30

            coords = []
            for i, (ch, b, cw) in enumerate(zip(chars, bboxes, widths)):
                dx = (cur_x + cw // 2) - (pad + total_w // 2)
                y_offset = int(arc_val * (dx ** 2)) if arc_val != 0 else 0
                coords.append((ch, cur_x, peak_y + y_offset))
                cur_x += cw + 2

            for step in range(depth_px, 0, -1):
                offset_y = step
                offset_x = int(step * 0.18)
                for ch, cx, cy in coords:
                    ld.text((cx + offset_x, cy + offset_y), ch, font=f, fill=extrude_c, stroke_width=2, stroke_fill=extrude_c)

            for ch, cx, cy in coords:
                if stroke_width > 0:
                    ld.text((cx, cy), ch, font=f, fill=front_c, stroke_width=stroke_width, stroke_fill=stroke_c)
                else:
                    ld.text((cx, cy), ch, font=f, fill=front_c)

            if angle_val != 0.0:
                layer = layer.rotate(angle_val, expand=True, resample=Image.Resampling.BICUBIC)

            lw, lh = layer.size
            cx_pos, cy_pos = center_pos
            target_canvas.alpha_composite(layer, (cx_pos - lw // 2, cy_pos - lh // 2))

        neon_yellow = _hex_to_rgba(z_loc["text"] or pal.get("main", "#DBFA11"))
        dark_green = _hex_to_rgba(z_loc["stroke"] or pal.get("sub", "#2A5101"))
        dark_stroke = (24, 52, 1, 255)

        # 区域 1：顶部微弧 3D 大字
        top_size = _zone_scaled(134 if len(top_text) <= 7 else 116, z_loc)
        top_x = tw // 2 + z_loc["off_x"]
        top_y = _clamp_element_y(230 + z_loc["off_y"], th)
        _render_3d_text_block(
            canvas,
            text_str=top_text,
            center_pos=(top_x, top_y),
            font_size=top_size,
            front_c=neon_yellow,
            extrude_c=dark_green,
            depth_px=24,
            angle_val=-2.5,
            arc_val=0.00015,
            stroke_width=3,
            stroke_c=dark_stroke
        )

        # 区域 2：胸前引导小标
        sub_c = _hex_to_rgba(z_sub["text"] or "#FFFFFF")
        sub_extrude = _hex_to_rgba(z_sub["stroke"] or dark_green)
        sub_size = _zone_scaled(76 if len(sub_hook) <= 10 else 66, z_sub)
        sub_x = tw // 2 + z_sub["off_x"]
        sub_y = _clamp_element_y(400 + z_sub["off_y"], th)
        _render_3d_text_block(
            canvas,
            text_str=sub_hook,
            center_pos=(sub_x, sub_y),
            font_size=sub_size,
            front_c=sub_c,
            extrude_c=sub_extrude,
            depth_px=14,
            angle_val=-2.0,
            arc_val=0.00010,
            stroke_width=2,
            stroke_c=dark_stroke
        )

        # 区域 3：底部转化标
        bot_c = _hex_to_rgba(z_main["text"] or "#FFFFFF")
        bot_extrude = _hex_to_rgba(z_main["stroke"] or dark_green)
        bot_size = _zone_scaled(96 if len(bot_hook) <= 9 else 84, z_main)
        bot_x = tw // 2 + z_main["off_x"]
        bot_y = _clamp_element_y(1720 + z_main["off_y"], th)
        _render_3d_text_block(
            canvas,
            text_str=bot_hook,
            center_pos=(bot_x, bot_y),
            font_size=bot_size,
            front_c=bot_c,
            extrude_c=bot_extrude,
            depth_px=18,
            angle_val=0.0,
            arc_val=0.0,
            stroke_width=3,
            stroke_c=dark_stroke
        )

        # 手绘白色放射射线 \ | /（支持独立上下左右全向拖拽）
        d_offs = getattr(config, "doodle_offsets", {}) or {}

        r_cfg = d_offs.get("rays_right") or {}
        r_dx = int(float(r_cfg.get("x", 0.0) or 0.0) * tw)
        r_dy = int(float(r_cfg.get("y", 0.0) or 0.0) * th)

        l_cfg = d_offs.get("rays_left") or {}
        l_dx = int(float(l_cfg.get("x", 0.0) or 0.0) * tw)
        l_dy = int(float(l_cfg.get("y", 0.0) or 0.0) * th)

        d = ImageDraw.Draw(canvas)

        # 右侧 3 束白光（随胸前小标联动 + 独立上下左右拖拽）
        rx, ry = 910 + r_dx, sub_y + r_dy
        d.line([(rx - 25, ry - 42), (rx + 48, ry - 66)], fill=(255, 255, 255, 250), width=9)
        d.line([(rx - 15, ry), (rx + 60, ry)], fill=(255, 255, 255, 250), width=9)
        d.line([(rx - 25, ry + 42), (rx + 48, ry + 66)], fill=(255, 255, 255, 250), width=9)

        # 底部左侧 3 束白光（随底部大标联动 + 独立上下左右拖拽）
        bx, by = 150 + l_dx, bot_y + l_dy
        d.line([(bx + 25, by - 42), (bx - 48, by - 66)], fill=(255, 255, 255, 250), width=9)
        d.line([(bx + 15, by), (bx - 60, by)], fill=(255, 255, 255, 250), width=9)
        d.line([(bx + 25, by + 42), (bx - 48, by + 66)], fill=(255, 255, 255, 250), width=9)

    else:
        # ---------------- 旧版模板兼容分支（存量工程继续可渲染） ----------------
        legacy = _legacy_palette(theme)
        draw = ImageDraw.Draw(canvas)

        if template_id == "gold_bold":
            gradient = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            g_draw = ImageDraw.Draw(gradient)
            for y in range(int(th * 0.55), th):
                alpha = int(140 * ((y - th * 0.55) / (th * 0.45)))
                g_draw.line([(0, y), (tw, y)], fill=(0, 0, 0, min(160, alpha)))
            canvas = Image.alpha_composite(canvas, gradient)
            draw = ImageDraw.Draw(canvas)

            lines = _wrap_text_to_lines(main_text, max_chars_per_line=8)
            font_size = 96 if max(len(l) for l in lines) <= 6 else 84
            main_font = get_font(font_size, bold=True, family=family)
            sub_font = get_font(44, bold=True, family=family)

            start_y = int(th * 0.65)
            if sub_text:
                sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
                sub_w = sub_bbox[2] - sub_bbox[0]
                sub_h = sub_bbox[3] - sub_bbox[1]
                pad_x, pad_y = 30, 14
                badge_x = (tw - (sub_w + pad_x * 2)) // 2
                badge_y = start_y - 80
                draw.rounded_rectangle(
                    [badge_x, badge_y, badge_x + sub_w + pad_x * 2, badge_y + sub_h + pad_y * 2],
                    radius=16,
                    fill=legacy["badge_bg"]
                )
                draw.text((badge_x + pad_x, badge_y + pad_y), sub_text, font=sub_font, fill=legacy["badge_fg"])

            curr_y = start_y
            for line in lines:
                l_bbox = draw.textbbox((0, 0), line, font=main_font)
                lw = l_bbox[2] - l_bbox[0]
                lh = l_bbox[3] - l_bbox[1]
                lx = (tw - lw) // 2
                for dx, dy in [(-3, -3), (-3, 3), (3, -3), (3, 3), (0, 4), (0, -4), (4, 0), (-4, 0)]:
                    draw.text((lx + dx, curr_y + dy), line, font=main_font, fill="#000000")
                draw.text((lx, curr_y), line, font=main_font, fill=legacy["primary"])
                curr_y += lh + 26

        elif template_id == "color_badge":
            lines = _wrap_text_to_lines(main_text, max_chars_per_line=7)
            font_size = 88 if max(len(l) for l in lines) <= 6 else 76
            main_font = get_font(font_size, bold=True, family=family)
            sub_font = get_font(42, bold=True, family=family)

            start_y = int(th * 0.62)
            if sub_text:
                s_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
                sw = s_bbox[2] - s_bbox[0]
                sh = s_bbox[3] - s_bbox[1]
                sx = (tw - (sw + 40)) // 2
                sy = start_y - 75
                draw.rounded_rectangle([sx, sy, sx + sw + 40, sy + sh + 20], radius=24, fill=legacy["badge_bg"])
                draw.text((sx + 20, sy + 10), sub_text, font=sub_font, fill=legacy["badge_fg"])

            curr_y = start_y
            for line in lines:
                l_bbox = draw.textbbox((0, 0), line, font=main_font)
                lw = l_bbox[2] - l_bbox[0]
                lh = l_bbox[3] - l_bbox[1]
                pad_x = 36
                pad_y = 16
                bx = (tw - (lw + pad_x * 2)) // 2
                by = curr_y
                draw.rounded_rectangle(
                    [bx, by, bx + lw + pad_x * 2, by + lh + pad_y * 2],
                    radius=14,
                    fill=legacy["badge_bg"]
                )
                draw.text((bx + pad_x, by + pad_y - 4), line, font=main_font, fill=legacy["badge_fg"])
                curr_y += lh + pad_y * 2 + 18

        else:  # dual_contrast
            sub_font = get_font(52, bold=True, family=family)
            main_font = get_font(88, bold=True, family=family)
            start_y = int(th * 0.64)

            if sub_text:
                s_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
                sw = s_bbox[2] - s_bbox[0]
                sx = (tw - sw) // 2
                for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                    draw.text((sx + dx, start_y + dy), sub_text, font=sub_font, fill="#000000")
                draw.text((sx, start_y), sub_text, font=sub_font, fill="#FFFFFF")
                start_y += 75

            lines = _wrap_text_to_lines(main_text, max_chars_per_line=8)
            curr_y = start_y
            for line in lines:
                l_bbox = draw.textbbox((0, 0), line, font=main_font)
                lw = l_bbox[2] - l_bbox[0]
                lh = l_bbox[3] - l_bbox[1]
                lx = (tw - lw) // 2
                for dx, dy in [(-3, -3), (-3, 3), (3, -3), (3, 3), (0, 4)]:
                    draw.text((lx + dx, curr_y + dy), line, font=main_font, fill="#000000")
                draw.text((lx, curr_y), line, font=main_font, fill=legacy["primary"])
                curr_y += lh + 22

    return canvas.convert("RGB")


def _probe_is_hdr_video(video_path: Path) -> bool:
    """探测视频是否为 iPhone HDR / HLG / BT.2020 / SMPTE2084 等高动态范围宽色域格式"""
    if not video_path.exists():
        return False
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=color_space,color_primaries,color_transfer,pix_fmt",
            "-of", "default=noprint_wrappers=1",
            str(video_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        out = (res.stdout or "").lower()
        return any(t in out for t in ("arib-std-b67", "smpte2084", "bt2020", "dovi"))
    except Exception:
        return False


def extract_candidate_frames(
    video_path: Path,
    output_dir: Path,
    timestamps: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """从视频中提取 3~5 个黄金候选帧（智能识别 HDR 并进行广播级色调映射，杜绝发白过曝）"""
    output_dir.mkdir(parents=True, exist_ok=True)
    if not video_path.exists():
        return []

    # 若未指定时间戳，通过 ffprobe 获取总时长
    if not timestamps:
        duration = 10.0
        try:
            probe = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if probe.returncode == 0 and probe.stdout.strip():
                duration = float(probe.stdout.strip())
        except Exception as e:
            logger.warning("探测视频时长异常: %s，回退默认 10 秒", e)

        # 提取 3 处候选时间点（避开前 1.5 秒和尾部；极短视频自动钳制到 0.5s 起始）
        timestamps = [
            round(max(0.5, duration * 0.18), 2),
            round(max(1.5, duration * 0.45), 2),
            round(max(2.5, duration * 0.72), 2),
        ]
    else:
        timestamps = [round(max(0.0, float(ts)), 3) for ts in timestamps]

    results = []
    labels = ["开场定格", "重点讲述", "焦点强调", "收尾展示"]

    video_mtime = video_path.stat().st_mtime if video_path.exists() else 0
    is_hdr: Optional[bool] = None

    for idx, ts in enumerate(timestamps):
        out_name = f"thumb_candidate_{idx}_{int(ts*100)}.jpg"
        out_file = output_dir / out_name
        label = labels[idx] if idx < len(labels) else f"候选帧 {idx+1}"

        # 缓存命中检测：若已提取且文件有效且新于视频源，直接复用，免去重复调用 ffmpeg
        if out_file.exists() and out_file.stat().st_size > 0 and out_file.stat().st_mtime >= video_mtime:
            results.append({
                "timestamp": ts,
                "label": label,
                "filename": out_name,
                "path": str(out_file)
            })
            continue

        if is_hdr is None:
            is_hdr = _probe_is_hdr_video(video_path)

        # 基础命令
        cmd = ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", str(video_path)]
        if is_hdr:
            # HDR HLG / BT.2020 注入广播级色调映射滤镜链，使绿树通透、肤色红润，彻底消除灰白惨白滤镜感
            cmd.extend([
                "-vf",
                "zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,"
                "zscale=p=bt709:t=bt709:m=bt709:r=limited,format=yuv420p,"
                "eq=contrast=1.10:brightness=-0.02:saturation=1.12"
            ])
        cmd.extend(["-frames:v", "1", "-q:v", "3", str(out_file)])

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

        # 环境滤镜缺失兜底：若带有 zscale 的命令执行失败，安全回退普通抽取
        if proc.returncode != 0 or not out_file.exists():
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", f"{ts:.3f}",
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "3",
                str(out_file)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

        if out_file.exists():
            results.append({
                "timestamp": ts,
                "label": label,
                "filename": out_name,
                "path": str(out_file)
            })

    return results
