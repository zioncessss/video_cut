from pathlib import Path
from typing import List, Dict, Any, Optional
import re

def format_timestamp_srt(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_timestamp_ass(seconds: float) -> str:
    """ASS 时间戳格式: H:MM:SS.cs (百分之一秒)"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"

def hex_to_ass_color(hex_color: str) -> str:
    """
    将 CSS hex 颜色 (#RRGGBB) 转换为 ASS 的 &H00BBGGRR& 格式。
    默认回退到金黄 (&H0015CCFA&)
    """
    if not hex_color:
        return "&H0015CCFA&"
    clean_hex = hex_color.lstrip("#")
    if len(clean_hex) == 6:
        r, g, b = clean_hex[0:2], clean_hex[2:4], clean_hex[4:6]
        return f"&H00{b}{g}{r}&"
    return "&H0015CCFA&"

def generate_srt_file(subtitles: List[Dict[str, Any]], output_path: Path) -> Path:
    """生成标准 SRT 字幕文件"""
    lines = []
    for idx, sub in enumerate(subtitles, start=1):
        start = format_timestamp_srt(sub.get("start_time", 0.0))
        end = format_timestamp_srt(sub.get("end_time", 0.0))
        text = sub.get("corrected_text") or sub.get("raw_text") or ""
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path

def generate_ass_file(
    subtitles: List[Dict[str, Any]],
    output_path: Path,
    strategy: Optional[Dict[str, Any]] = None
) -> Path:
    """
    生成带主题样式与行内关键词高亮变色的 ASS 高级字幕文件。
    支持 4 种视觉主题: viral_gold, tech_emerald, marker_pen, minimal_white。
    """
    strat = strategy or {}
    show_subtitles = strat.get("show_subtitles", True)
    if not show_subtitles:
        # 用户选择隐藏字幕，生成空的 ASS 文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nTitle: VideoCut Subtitles\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        return output_path

    theme = strat.get("subtitle_theme", "glow_gold")
    font_size_str = strat.get("font_size", "medium")
    # 字号映射：小=42，中=52，大=64，特大=76
    font_size_map = {"small": 42, "medium": 52, "large": 64, "xlarge": 76}
    chosen_font_size = font_size_map.get(font_size_str, 52)

    # 垂直位置映射 (subtitle_position_y: 距离顶部百分比，默认 82%)
    # ASS MarginV 表示距离底部的边距：1920 * (100 - y) / 100
    pos_y_percent = strat.get("subtitle_position_y", 82)
    margin_v = max(40, min(1800, int(1920 * (100 - pos_y_percent) / 100)))

    enable_hl = strat.get("enable_highlight", True)
    hl_color_hex = strat.get("highlight_color", "#FACC15")
    hl_scale = strat.get("highlight_scale", True)
    custom_words = strat.get("custom_highlight_words", [])

    # 主题样式表模板:
    # 格式: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # BorderStyle: 1=Outline + drop shadow (无黑底，自然融入画面), 3=Opaque box (带底框)
    theme_templates = {
        # 1. 纯净发光金黄 (完全融入画面，无黑色底框，高亮词发光变金黄)
        "glow_gold": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H60000000,-1,0,0,0,100,100,2,0,1,3,2,2,40,40,{margin_v},1",
        # 2. 超透毛玻璃白 (仅带极微弱磨砂透明轮廓，不遮挡画面细节)
        "glass_clean": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00333333,&H30000000,-1,0,0,0,100,100,1,0,1,2,1,2,40,40,{margin_v},1",
        # 3. 电影级自然立体白 (柔和多层立体投影，无黑底框)
        "cinema_shadow": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,2,4,2,40,40,{margin_v},1",
        # 4. 科技翡翠
        "tech_emerald": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H001A1A1A,&H6010B981,-1,0,0,0,100,100,3,0,1,2,2,2,40,40,{margin_v},1",
        # 5. 爆款黑底胶囊金
        "viral_gold": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,3,0,0,2,40,40,{margin_v},1",
        # 6. 教学记号笔
        "marker_pen": "Style: Default,Microsoft YaHei,{fontsize},&H00111111,&H000000FF,&H00FFFFFF,&H00FEF08A,-1,0,0,0,100,100,2,0,3,0,0,2,40,40,{margin_v},1",
    }
    style_template = theme_templates.get(theme, theme_templates["glow_gold"])
    selected_style = style_template.format(fontsize=chosen_font_size, margin_v=margin_v)
    ass_hl_color = hex_to_ass_color(hl_color_hex)
    scale_tag = r"\fscx110\fscy110" if hl_scale else ""
    reset_scale_tag = r"\fscx100\fscy100" if hl_scale else ""

    ass_header = f"""[Script Info]
Title: VideoCut Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{selected_style}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for sub in subtitles:
        start = format_timestamp_ass(sub.get("start_time", 0.0))
        end = format_timestamp_ass(sub.get("end_time", 0.0))
        text = sub.get("corrected_text") or sub.get("raw_text") or ""
        
        # 提取当前片段要高亮的关键词列表
        matched = list(sub.get("matched_keywords", [])) + list(custom_words)
        matched = [w.strip() for w in matched if w.strip()]

        styled_text = text
        if enable_hl and matched and text:
            # 排序优先长词替换
            matched.sort(key=len, reverse=True)
            pattern = "(" + "|".join(re.escape(w) for w in matched) + ")"
            # ASS 行内高亮变色: {\c&H...&\b1\fscx110\fscy110}高亮词{\r}
            # \r 重置为样式默认颜色
            replacement = rf"{{\\c{ass_hl_color}\\b1{scale_tag}}}\1{{\\r{reset_scale_tag}}}"
            try:
                styled_text = re.sub(pattern, replacement, text)
            except Exception:
                styled_text = text

        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{styled_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(events) + "\n")
    return output_path

