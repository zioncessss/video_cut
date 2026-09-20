import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.native_engine.ffmpeg_filter import composer
from app.models.entities import KeptSpan, PruneSpan, CutProject, SubtitleSegment, EditingStrategy, MaterialCategory

def test_compose_with_kept_spans_and_anti_pop(tmp_path, monkeypatch):
    """验证提供 kept_spans 时，FFmpeg 滤镜包含 15ms afade 音频防爆音与音视频切片拼接"""
    th = tmp_path / "talking_head.mp4"
    th.write_bytes(b"th_dummy_bytes")
    out = tmp_path / "output_compact.mp4"

    kept_spans = [
        KeptSpan(start_time=0.20, end_time=3.50, duration=3.30, audio_fade=True),
        KeptSpan(start_time=4.80, end_time=10.00, duration=5.20, audio_fade=True)
    ]

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
        broll_cuts=[],
        output_path=out,
        aspect_ratio="9:16",
        total_duration=8.50,
        strategy={"video_speed": 1.0},
        kept_spans=kept_spans
    )

    assert success is True
    assert out.exists()

    filter_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[filter_idx + 1]

    # 验证音频切片与 15ms afade 防爆音注入
    assert "afade=t=in:ss=0:d=0.015" in fc
    assert "afade=t=out:st=3.285:d=0.015" in fc
    assert "afade=t=out:st=5.185:d=0.015" in fc

    # 验证视频切片与拼接
    assert "[0:v]trim=start=0.2:end=3.5" in fc
    assert "[0:v]trim=start=4.8:end=10.0" in fc
    assert "concat=n=2:v=1:a=0[v_base]" in fc
    assert "concat=n=2:v=0:a=1[a_base]" in fc

def test_compose_kept_spans_with_broll_overlay(tmp_path, monkeypatch):
    """验证在粗剪紧凑时间轴上，B-roll 通过 overlay 滤镜无缝对齐"""
    th = tmp_path / "th.mp4"
    th.write_bytes(b"th")
    broll = tmp_path / "broll.mp4"
    broll.write_bytes(b"broll")
    out = tmp_path / "out.mp4"

    kept_spans = [
        KeptSpan(start_time=1.0, end_time=6.0, duration=5.0, audio_fade=True),
        KeptSpan(start_time=8.0, end_time=13.0, duration=5.0, audio_fade=True)
    ]
    brolls = [
        {
            "start_time": 2.0,
            "end_time": 4.0,
            "material_path": broll,
            "transition": 0.0
        }
    ]

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
        total_duration=10.0,
        strategy={"video_speed": 1.0},
        kept_spans=kept_spans
    )

    assert success is True
    filter_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[filter_idx + 1]

    # 验证 B-roll overlay 挂在紧凑时间轴
    assert "overlay=0:0:enable='between(t,2.000,4.000)'" in fc

def test_toggle_subtitle_prune_and_config_api(tmp_path, monkeypatch):
    """验证 toggle-prune 与 prune-config REST API 端点功能与状态可逆性"""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.native_engine.project_storage import project_storage_service
    from app.native_engine.storage import storage_service
    from app.models.entities import Material

    client = TestClient(app)

    # 准备测试素材与工程
    mat_id = "test_prune_mat_001"
    mat = Material(
        id=mat_id,
        category=MaterialCategory.TALKING_HEAD,
        filename="test_mat.mp4",
        filepath="materials/test_mat.mp4",
        duration=20.0,
        width=1080,
        height=1920,
        fps=30.0
    )
    storage_service._cache[mat_id] = mat
    storage_service.repo.save(mat)

    p = CutProject(
        id="test_prune_proj_001",
        title="测试粗剪工程",
        talking_head_id=mat_id,
        subtitles=[
            SubtitleSegment(id="sub_1", start_time=0.5, end_time=2.0, raw_text="第一句正常", corrected_text="第一句正常"),
            SubtitleSegment(id="sub_2", start_time=2.5, end_time=4.0, raw_text="口误前句", corrected_text="口误前句", is_pruned=True, prune_reason="retake_discard"),
            SubtitleSegment(id="sub_3", start_time=4.5, end_time=6.0, raw_text="口误后句", corrected_text="口误后句")
        ],
        prune_spans=[
            PruneSpan(id="span_1", start_time=2.5, end_time=4.3, reason="retake_discard", source_subtitle_id="sub_2", duration=1.8, is_active=True)
        ]
    )
    project_storage_service.save_project(p)

    # 1. 测试将已剔除的 sub_2 恢复 (toggle-prune)
    res = client.post(f"/api/v1/projects/{p.id}/subtitles/sub_2/toggle-prune", json={"is_pruned": False})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["is_pruned"] is False
    # 验证 prune_spans 中对应 span 变为非 active
    active_spans = [s for s in data["prune_spans"] if s["is_active"]]
    assert len(active_spans) == 0

    # 2. 再次切换：将 sub_1 标记为剔除
    res2 = client.post(f"/api/v1/projects/{p.id}/subtitles/sub_1/toggle-prune")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["is_pruned"] is True
    active_spans2 = [s for s in data2["prune_spans"] if s["is_active"]]
    assert len(active_spans2) == 1
    assert active_spans2[0]["source_subtitle_id"] == "sub_1"

    # 3. 测试更新粗剪配置 (prune-config)
    res3 = client.post(f"/api/v1/projects/{p.id}/prune-config", json={
        "enable_head_prune": True,
        "head_padding_seconds": 0.15
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["success"] is True
    assert "total_pruned_seconds" in data3
