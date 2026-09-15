import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.ffmpeg_filter import composer
from app.native_engine.subtitle_styler import generate_srt_file

def test_subtitle_styler(tmp_path):
    subtitles = [
        {"start_time": 1.2, "end_time": 4.5, "corrected_text": "今天看标准化场地"},
        {"start_time": 4.6, "end_time": 8.0, "corrected_text": "科目二倒车入库一把过"}
    ]
    srt_out = tmp_path / "test.srt"
    res = generate_srt_file(subtitles, srt_out)
    assert res.exists()
    content = res.read_text(encoding="utf-8")
    assert "00:00:01,200 --> 00:00:04,500" in content
    assert "今天看标准化场地" in content

def test_scale_filter_builder():
    filter_916 = composer.build_scale_filter("9:16")
    assert "1080:1920" in filter_916

    filter_169 = composer.build_scale_filter("16:9")
    assert "1920:1080" in filter_169
