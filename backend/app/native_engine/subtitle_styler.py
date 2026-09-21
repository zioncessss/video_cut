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

def wrap_long_subtitle(text: str, max_line_len: int = 15, protected_words: Optional[List[str]] = None) -> str:
    """
    针对超长单行字幕（>15字，9:16竖屏排版兜底阈值），在自然语法助词、连词、标点或中心点插入 \\N 智能折行，
    常规口播（<=15字）100% 保持单行展示；若必须折行，严禁弱连词挂尾，并避开保护词中间断裂。
    """
    if not text or len(text) <= max_line_len or r"\N" in text or "\n" in text:
        return text

    protected_ranges = []
    if protected_words:
        for w in protected_words:
            if w and w in text:
                idx = 0
                while True:
                    p = text.find(w, idx)
                    if p == -1:
                        break
                    protected_ranges.append((p, p + len(w)))
                    idx = p + 1

    def is_protected(pos: int) -> bool:
        return any(start < pos < end for start, end in protected_ranges)

    # 优先在自然标点、语气助词或连词前断句折行，避开保护词且严禁弱连词（和/与/在等）挂在前半句末尾
    dangling_chars = ("和", "与", "跟", "及", "同", "在", "从", "到", "向", "由", "把", "让")
    split_candidates = [
        m.start() for m in re.finditer(r'[，,。？！?!；;]|(?<=[呢吧啊吗呀啦哒哦哈])|(?=(?:还|并且|但是|而且|然后|或者|包括|我们|你们|他们|其实|大家|全部|手把手))', text)
        if 3 <= m.start() <= len(text) - 3
        and not is_protected(m.start())
        and not any(text[:m.start()].rstrip("，, ").endswith(d) for d in dangling_chars)
    ]
    if split_candidates:
        mid = len(text) / 2
        best_pos = min(split_candidates, key=lambda p: abs(p - mid))
        return text[:best_pos].rstrip("，, ") + r"\N" + text[best_pos:].lstrip("，, ")

    # 若无明显连词/标点，在几何中点折行（若中点落在保护词内，则平移至保护词边缘）
    mid_idx = len(text) // 2
    for start, end in protected_ranges:
        if start < mid_idx < end:
            mid_idx = start if (mid_idx - start) <= (end - mid_idx) else end
            break
    return text[:mid_idx] + r"\N" + text[mid_idx:]

def smooth_subtitle_timings(
    subtitles: List[Dict[str, Any]],
    lead_in: float = 0.07,
    max_fill_gap: float = 0.60,
    trailing_hold: float = 0.25,
    final_hold: float = 0.30
) -> List[Dict[str, Any]]:
    """时序平滑：70ms 听觉前置缓冲与自然微停顿无缝接力，消除闪烁黑屏"""
    if not subtitles:
        return []

    smoothed = []
    for i, s in enumerate(subtitles):
        item = dict(s)
        curr_start = float(item.get("start_time", 0.0))
        curr_end = float(item.get("end_time", 0.0))

        if i > 0:
            prev_end = float(smoothed[i - 1].get("end_time", 0.0))
            eff_start = max(prev_end, round(curr_start - lead_in, 3))
        else:
            eff_start = max(0.0, round(curr_start - lead_in, 3))

        if i + 1 < len(subtitles):
            next_start = float(subtitles[i + 1].get("start_time", 0.0))
            gap = round(next_start - curr_end, 3)
            if 0 < gap <= max_fill_gap:
                next_eff_start = max(curr_end, round(next_start - lead_in, 3))
                eff_end = next_eff_start
            else:
                eff_end = min(next_start, round(curr_end + trailing_hold, 3))
        else:
            eff_end = round(curr_end + final_hold, 3)

        if eff_end <= eff_start:
            eff_end = max(eff_start + 0.3, curr_end)

        item["start_time"] = eff_start
        item["end_time"] = eff_end
        smoothed.append(item)

    return smoothed

def generate_srt_file(
    subtitles: List[Dict[str, Any]],
    output_path: Path,
    smooth_timings: bool = False
) -> Path:
    """生成标准 SRT 字幕文件"""
    smoothed = smooth_subtitle_timings(subtitles) if smooth_timings else subtitles
    lines = []
    for idx, sub in enumerate(smoothed, start=1):
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
    strategy: Optional[Dict[str, Any]] = None,
    smooth_timings: bool = False
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

    theme = strat.get("subtitle_theme", "cinema_shadow")
    font_size_val = strat.get("subtitle_font_size") or strat.get("font_size", "medium")
    if isinstance(font_size_val, (int, float)):
        chosen_font_size = int(font_size_val)
    elif str(font_size_val).isdigit():
        chosen_font_size = int(font_size_val)
    else:
        # 针对 1080x1920 竖屏优化的黄金短视频视读字号体系 (标准 72px 对应约 55% 画面横幅比例)
        font_size_map = {"small": 56, "medium": 72, "large": 86, "xlarge": 98}
        chosen_font_size = font_size_map.get(str(font_size_val), 72)

    # 2D 水平与垂直位置映射 (固定 50% 水平居中，74% 口播黄金推荐区，避开人脸与底部控制栏)
    pos_x_percent = strat.get("subtitle_position_x", 50)
    pos_y_percent = strat.get("subtitle_position_y", 74)
    ass_x = int(1080 * pos_x_percent / 100)
    ass_y = int(1920 * pos_y_percent / 100)
    margin_v = max(40, min(1800, int(1920 * (100 - pos_y_percent) / 100)))

    # 水平最大边界 (默认 100% 全宽锁定，左右预留 24px 安全内边距)
    sub_w_percent = strat.get("subtitle_width_percent")
    if sub_w_percent is None:
        sub_w_percent = 100
    margin_h = max(24, min(400, int(1080 * (100 - sub_w_percent) / 200)))

    # 字体映射表 (针对 Windows 与跨平台 FFmpeg libass 渲染引擎)
    # notoserif 选用 Windows 原生高品质中粗宋体 STZhongsong (华文中宋)，彻底解决可变字体 NotoSerifSC-VF.ttf 在 libass 下被回退为 ExtraLight 极细体的缺陷
    font_family_map = {
        "notoserif": "STZhongsong",   # 华文中宋 (电影首选，横细竖粗，解决可变字体 ExtraLight Bug)
        "fangsong": "FangSong",       # 清雅仿宋 (文学剧本文风，挺拔清秀)
        "songti": "SimSun",           # 经典宋体 (端庄书卷感)
        "kaiti": "KaiTi",             # 书法楷体 (原图同款 · 叙事温润)
        "yahei": "Microsoft YaHei",   # 现代清晰黑体
        "hei": "SimHei",              # 经典黑体
    }
    raw_font = str(strat.get("subtitle_font_family") or "notoserif").lower()
    chosen_font_name = font_family_map.get(raw_font, "STZhongsong")

    enable_hl = strat.get("enable_highlight", True)
    hl_color_hex = strat.get("highlight_color", "#FBBF24")
    hl_scale = strat.get("highlight_scale", True)
    custom_words = strat.get("custom_highlight_words", [])

    # 主题样式表模板:
    # 格式: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    # BorderStyle: 1=Outline + drop shadow (无黑底，自然融入画面), 3=Opaque box (带底框)
    theme_templates = {
        # 1. 电影级自然立体白 (方案 A：Outline 0.6 半透羽化微边缘 + Shadow 1.8 紧凑微阴影，纯白字身饱满立体)
        "cinema_shadow": "Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H40000000,&H70000000,-1,0,0,0,100,100,1,0,1,0.6,1.8,2,{margin_h},{margin_h},{margin_v},1",
        # 2. 纯净发光金黄 (方案 A：Outline 0.6 半透羽化微边缘 + Shadow 1.8 紧凑微阴影，高亮词金黄发光)
        "glow_gold": "Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H40000000,&H70000000,-1,0,0,0,100,100,1,0,1,0.6,1.8,2,{margin_h},{margin_h},{margin_v},1",
        # 3. 超透毛玻璃白 (仅带极微弱磨砂轮廓，不遮挡画面细节)
        "glass_clean": "Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H00222222,&H50000000,-1,0,0,0,100,100,1,0,1,1.5,2.5,2,{margin_h},{margin_h},{margin_v},1",
        # 4. 科技翡翠
        "tech_emerald": "Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H00111111,&H6010B981,-1,0,0,0,100,100,1,0,1,1.8,2.8,2,{margin_h},{margin_h},{margin_v},1",
        # 5. 爆款黑底胶囊金
        "viral_gold": "Style: Default,{fontname},{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,3,0,0,2,{margin_h},{margin_h},{margin_v},1",
        # 6. 教学记号笔
        "marker_pen": "Style: Default,{fontname},{fontsize},&H00111111,&H000000FF,&H00FFFFFF,&H00FEF08A,-1,0,0,0,100,100,1,0,3,0,0,2,{margin_h},{margin_h},{margin_v},1",
    }
    style_template = theme_templates.get(theme, theme_templates["glow_gold"])
    selected_style = style_template.format(fontname=chosen_font_name, fontsize=chosen_font_size, margin_h=margin_h, margin_v=margin_v)
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
    should_smooth = smooth_timings or strat.get("smooth_timings", False)
    smoothed = smooth_subtitle_timings(subtitles) if should_smooth else subtitles
    for sub in smoothed:
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
                        word_color = str(w.get("color") or hl_color_hex).strip()
                        ass_c = hex_to_ass_color(word_color)
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

        # 零信任防御兜底：若策略开启高亮但上游未传或丢失高亮词，就地触发规则引擎提取高光词
        if enable_hl and not matched and text:
            try:
                from app.native_engine.keyword_matcher import build_highlight_words
                auto_hws = build_highlight_words(text)
                for w in auto_hws:
                    if isinstance(w, dict) and w.get("word"):
                        w_text = str(w["word"]).strip()
                        if w_text:
                            word_color = str(w.get("color") or hl_color_hex).strip()
                            ass_c = hex_to_ass_color(word_color)
                            word_ass_colors[w_text] = ass_c
                            matched.append(w_text)
            except Exception:
                pass

        # 9:16 竖屏单行优先（<=15字不换行），且避开高亮保护词中间截断与弱连词挂尾
        text = wrap_long_subtitle(text, max_line_len=15, protected_words=matched)

        styled_text = text
        if enable_hl and matched and text:
            # 排序优先长词替换
            matched.sort(key=len, reverse=True)
            pattern = "(" + "|".join(re.escape(w) for w in matched) + ")"
            # ASS 行内高亮变色: 纯白高亮通过 122% 放大并加粗强调；彩色高亮通过变色+115%强调
            def _hl_replace(m):
                w_str = m.group(0)
                w_color = word_ass_colors.get(w_str, ass_hl_color)
                upper_c = w_color.upper()
                is_white = upper_c in ("&H00FFFFFF&", "&HFFFFFF&")
                if is_white:
                    # 纯白高亮：122% 字号 + 加粗，与前端预览 1:1 杂志感强调
                    return r"{\b1\fscx122\fscy122}" + w_str + r"{\r" + reset_scale_tag + "}"
                else:
                    return r"{\c" + w_color + r"\b1" + scale_tag + "}" + w_str + r"{\r" + reset_scale_tag + "}"
            try:
                styled_text = re.sub(pattern, _hl_replace, text)
            except Exception:
                styled_text = text

        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{pos_tag}{styled_text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path

