import pytest
from pathlib import Path
from app.native_engine.ffmpeg_filter import composer
from app.models.entities import KeptSpan

def test_broll_source_trim_in_filter(tmp_path, monkeypatch):
    th = tmp_path / "talking_head.mp4"
    th.write_bytes(b"th_dummy")
    broll = tmp_path / "broll.mp4"
    broll.write_bytes(b"broll_dummy")
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

    # 带有自定义素材截取 In 点 source_start_time = 1.8s
    broll_cuts = [
        {
            "start_time": 2.5,
            "end_time": 5.6,
            "source_start_time": 1.8,
            "material_path": str(broll),
            "transition": 0.0
        }
    ]

    kept_spans = [
        KeptSpan(start_time=0.0, end_time=10.0, duration=10.0, audio_fade=True)
    ]

    success = composer.compose_jl_cut(
        talking_head_path=th,
        broll_cuts=broll_cuts,
        output_path=out,
        aspect_ratio="9:16",
        total_duration=10.0,
        kept_spans=kept_spans
    )

    assert success is True
    filter_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[filter_idx + 1]

    # 断言分镜从 source_start_time = 1.800 截取
    assert "trim=start=1.8" in fc, f"滤镜中应包含素材 In 点截取 trim=start=1.8，实际生成: {fc}"
