from pathlib import Path
from typing import List, Dict, Any

def format_timestamp_srt(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

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
