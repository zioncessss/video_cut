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

def test_compose_without_ffmpeg_must_raise(tmp_path, monkeypatch):
    """真实执行铁律回归：FFmpeg 缺失时严禁复制原文件假装合成成功，必须抛出真实异常"""
    src = tmp_path / "talking_head.mp4"
    src.write_bytes(b"x" * 20480)  # >10KB 真实体量的模拟素材
    out = tmp_path / "output.mp4"

    monkeypatch.setattr(composer, "has_ffmpeg", False)
    with pytest.raises(RuntimeError, match="FFmpeg"):
        composer.compose_jl_cut(
            talking_head_path=src,
            broll_cuts=[],
            output_path=out,
            aspect_ratio="9:16",
            total_duration=3.0,
        )
    # 失败路径不得产出任何输出文件
    assert not out.exists()

def test_multi_broll_input_indices(tmp_path, monkeypatch):
    """验证包含多个 B-roll（超过 5 段）时，FFmpeg 的 filtergraph 输入索引连续单调递增，杜绝 input_idx 越界"""
    th = tmp_path / "th.mp4"
    th.write_bytes(b"th")
    brolls = []
    for i in range(8):
        b = tmp_path / f"broll_{i}.mp4"
        b.write_bytes(b"broll")
        brolls.append({
            "start_time": float(i * 2 + 1),
            "end_time": float(i * 2 + 2),
            "material_path": b,
            "transition": 0.0
        })
    out = tmp_path / "out.mp4"

    captured_cmd = []
    def fake_run(cmd, *args, **kwargs):
        captured_cmd.extend(cmd)
        class Res:
            returncode = 0
            stderr = b""
        out.write_bytes(b"ok")
        return Res()

    monkeypatch.setattr("subprocess.run", fake_run)
    success = composer.compose_jl_cut(
        talking_head_path=th,
        broll_cuts=brolls,
        output_path=out,
        aspect_ratio="9:16",
        total_duration=20.0
    )
    assert success is True
    filter_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[filter_idx + 1]
    # 8 个 broll 的 input_idx 必须依次为 1 到 8 严格连续
    for i in range(1, 9):
        assert f"[{i}:v]trim=" in fc
    assert "[13:v]" not in fc
