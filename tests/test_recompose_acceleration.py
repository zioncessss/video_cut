import pytest
import subprocess
from pathlib import Path
from app.native_engine.ffmpeg_filter import composer
from app.models.entities import KeptSpan

def test_broll_pipeline_no_infinite_stream_loop(tmp_path, monkeypatch):
    """
    验证 018 性能优化：
    B-roll 空镜输入彻底废止 -stream_loop -1 无限循环解码，
    且在 overlay 滤镜中自动配置 eof_action=repeat 保护防提前 EOF。
    """
    th = tmp_path / "th_test.mp4"
    th.write_bytes(b"dummy_th_content")
    broll1 = tmp_path / "broll_1.mp4"
    broll1.write_bytes(b"dummy_broll_1")
    broll2 = tmp_path / "broll_2.mp4"
    broll2.write_bytes(b"dummy_broll_2")
    out = tmp_path / "out_accel.mp4"

    captured_cmd = []

    def mock_run(cmd, *args, **kwargs):
        captured_cmd.extend(cmd)
        class Res:
            returncode = 0
            stderr = b""
        out.write_bytes(b"fake_output_bytes")
        return Res()

    monkeypatch.setattr(subprocess, "run", mock_run)

    broll_cuts = [
        {
            "start_time": 1.0,
            "end_time": 4.0,
            "source_start_time": 0.5,
            "material_path": str(broll1),
            "transition": 0.0
        },
        {
            "start_time": 5.0,
            "end_time": 8.0,
            "source_start_time": 0.0,
            "material_path": str(broll2),
            "transition": 0.2
        }
    ]

    kept_spans = [
        KeptSpan(start_time=0.0, end_time=10.0, duration=10.0, audio_fade=True)
    ]

    ok = composer.compose_jl_cut(
        talking_head_path=th,
        broll_cuts=broll_cuts,
        output_path=out,
        aspect_ratio="9:16",
        total_duration=10.0,
        kept_spans=kept_spans
    )

    assert ok is True
    # 核心断言 1: 命令参数中绝不含有 "-stream_loop -1"
    assert "-stream_loop" not in captured_cmd, f"优化后严禁出现 -stream_loop，实际命令: {captured_cmd}"

    # 核心断言 2: FilterGraph 中 overlay 必须配置 eof_action=repeat
    fc_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[fc_idx + 1]
    assert "eof_action=repeat" in fc, f"FilterGraph overlay 必须附带 eof_action=repeat，实际: {fc}"


def test_hdr_probe_persistent_caching(tmp_path, monkeypatch):
    """
    验证 018 性能优化：
    素材 HDR 规格探测具备 mtime 级持久化内存缓存，
    同一素材多次渲染或多处调用时，ffprobe 命令行子进程仅调用 1 次，后续完全命中缓存。
    """
    test_video = tmp_path / "sample_video.mp4"
    test_video.write_bytes(b"sample_bytes_for_hdr")

    probe_count = 0

    def mock_run(cmd, *args, **kwargs):
        nonlocal probe_count
        if "ffprobe" in cmd[0]:
            probe_count += 1
            class Res:
                returncode = 0
                stdout = b"color_transfer=arib-std-b67\ncolor_primaries=bt2020\n"
                stderr = b""
            return Res()
        raise NotImplementedError()

    monkeypatch.setattr(subprocess, "run", mock_run)

    # 清空可能存在的缓存
    composer._hdr_cache.clear()

    # 第一次探测：触发 ffprobe
    res1 = composer.is_hdr_video(test_video)
    assert res1 is True
    assert probe_count == 1, f"初次调用应执行 1 次 ffprobe，实际: {probe_count}"

    # 第二次探测：必须命中持久化内存缓存，零进程唤起
    res2 = composer.is_hdr_video(test_video)
    assert res2 is True
    assert probe_count == 1, f"第二次调用必须命中缓存不启动子进程，实际: {probe_count}"

    # 第三次探测（不同 Path 对象但指向同一文件）：同样命中缓存
    res3 = composer.is_hdr_video(Path(str(test_video)))
    assert res3 is True
    assert probe_count == 1
