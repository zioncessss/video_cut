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
    output_path.write_text("\n".join(lines), encoding="utf-8")
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
        output_path.write_text("[Script Info]\nTitle: VideoCut Subtitles\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n", encoding="utf-8")
        return output_path

    theme = strat.get("subtitle_theme", "glow_gold")
    font_size_val = strat.get("subtitle_font_size") or strat.get("font_size", "medium")
    if isinstance(font_size_val, (int, float)):
        chosen_font_size = int(font_size_val)
    elif str(font_size_val).isdigit():
        chosen_font_size = int(font_size_val)
    else:
        # 针对 1080x1920 竖屏优化的黄金短视频视读字号体系 (标准 72px 对应约 55% 画面横幅比例)
        font_size_map = {"small": 56, "medium": 72, "large": 86, "xlarge": 98}
        chosen_font_size = font_size_map.get(str(font_size_val), 72)

    # 2D 水平与垂直位置映射 (默认 50% 水平居中，82% 黄金底部)
    pos_x_percent = strat.get("subtitle_position_x", 50)
    pos_y_percent = strat.get("subtitle_position_y", 82)
    ass_x = int(1080 * pos_x_percent / 100)
    ass_y = int(1920 * pos_y_percent / 100)
    margin_v = max(40, min(1800, int(1920 * (100 - pos_y_percent) / 100)))

    # 水平最大边界 (支持拖拽拉宽/收窄字幕最大换行宽度)
    sub_w_percent = strat.get("subtitle_width_percent") or 90
    margin_h = max(20, min(400, int(1080 * (100 - sub_w_percent) / 200)))

    enable_hl = strat.get("enable_highlight", True)
    hl_color_hex = strat.get("highlight_color", "#FACC15")
    hl_scale = strat.get("highlight_scale", True)
    custom_words = strat.get("custom_highlight_words", [])

    # 主题样式表模板:
    # 格式: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # BorderStyle: 1=Outline + drop shadow (无黑底，自然融入画面), 3=Opaque box (带底框)
    theme_templates = {
        # 1. 纯净发光金黄 (完全融入画面，无黑色底框，高对比极细描边与柔和立体投影，彻底杜绝粗黑描边导致汉字笔画糊化失真)
        "glow_gold": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H70000000,-1,0,0,0,100,100,1,0,1,1.2,2.5,2,{margin_h},{margin_h},{margin_v},1",
        # 2. 超透毛玻璃白 (仅带极微弱磨砂轮廓，不遮挡画面细节)
        "glass_clean": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00222222,&H50000000,-1,0,0,0,100,100,1,0,1,1.0,2.0,2,{margin_h},{margin_h},{margin_v},1",
        # 3. 电影级自然立体白 (柔和多层立体投影，无黑底框)
        "cinema_shadow": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,1.0,3.0,2,{margin_h},{margin_h},{margin_v},1",
        # 4. 科技翡翠
        "tech_emerald": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00111111,&H6010B981,-1,0,0,0,100,100,1,0,1,1.2,2.5,2,{margin_h},{margin_h},{margin_v},1",
        # 5. 爆款黑底胶囊金
        "viral_gold": "Style: Default,Microsoft YaHei,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,3,0,0,2,{margin_h},{margin_h},{margin_v},1",
        # 6. 教学记号笔
        "marker_pen": "Style: Default,Microsoft YaHei,{fontsize},&H00111111,&H000000FF,&H00FFFFFF,&H00FEF08A,-1,0,0,0,100,100,1,0,3,0,0,2,{margin_h},{margin_h},{margin_v},1",
    }
    style_template = theme_templates.get(theme, theme_templates["glow_gold"])
    selected_style = style_template.format(fontsize=chosen_font_size, margin_h=margin_h, margin_v=margin_v)
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
    pos_tag = rf"{{\an5\pos({ass_x},{ass_y})}}"
    for sub in subtitles:
        start = format_timestamp_ass(sub.get("start_time", 0.0))
        end = format_timestamp_ass(sub.get("end_time", 0.0))
        text = sub.get("corrected_text") or sub.get("raw_text") or ""
        
        # 提取当前片段要高亮的关键词列表与各自专属颜色
        hl_items = sub.get("highlight_words")
        word_ass_colors: Dict[str, str] = {}
        matched: List[str] = []
        if hl_items:
            for w in hl_items:
                if isinstance(w, dict) and w.get("word"):
                    w_text = str(w["word"]).strip()
                    if w_text:
                        # 转换 HEX 为 ASS 的 BGR 格式 (&HBBGGRR&)
                        h_code = str(w.get("color") or hl_color_hex).strip().lstrip("#")
                        if len(h_code) == 3:
                            h_code = "".join(c * 2 for c in h_code)
                        if len(h_code) == 6:
                            ass_c = f"&H{h_code[4:6].upper()}{h_code[2:4].upper()}{h_code[0:2].upper()}&"
                        else:
                            ass_c = ass_hl_color
                        word_ass_colors[w_text] = ass_c
                        matched.append(w_text)
        else:
            for kw in sub.get("matched_keywords", []):
                kws = str(kw).strip()
                if kws:
                    word_ass_colors[kws] = ass_hl_color
                    matched.append(kws)

        for cw in custom_words:
            cws = str(cw).strip()
            if cws and cws not in word_ass_colors:
                word_ass_colors[cws] = ass_hl_color
                matched.append(cws)

        styled_text = text
        if enable_hl and matched and text:
            # 排序优先长词替换
            matched.sort(key=len, reverse=True)
            pattern = "(" + "|".join(re.escape(w) for w in matched) + ")"
            # ASS 行内高亮变色: {\c&H...&\b1\fscx110\fscy110}高亮词{\r\fscx100\fscy100}
            def _hl_replace(m):
                w_str = m.group(0)
                w_color = word_ass_colors.get(w_str, ass_hl_color)
                return r"{\c" + w_color + r"\b1" + scale_tag + "}" + w_str + r"{\r" + reset_scale_tag + "}"
            try:
                styled_text = re.sub(pattern, _hl_replace, text)
            except Exception:
                styled_text = text

        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{styled_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path

