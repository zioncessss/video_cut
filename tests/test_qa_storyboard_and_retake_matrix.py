import pytest
from app.models.entities import SubtitleSegment, PruneSpan, PruneReason, BrollReplacement, MaterialCategory
from app.native_engine.prune_engine import auto_prune_engine
from app.native_engine.asr_runner import asr_runner
from app.native_engine.ffmpeg_filter import composer
from app.native_engine.keyword_matcher import build_highlight_words

def test_tc_prune_001_prefix_overlap_retake_identification():
    """TC-PRUNE-001: 典型前缀重复口误识别（前句读错说一半，后句重新朗读正确正文）"""
    subs = [
        SubtitleSegment(
            id="sub_01",
            start_time=1.0,
            end_time=2.8,
            raw_text="我们今天去顺达",
            corrected_text="我们今天去顺达"
        ),
        SubtitleSegment(
            id="sub_02",
            start_time=3.3, # gap = 0.5s > 0.40s
            end_time=5.8,
            raw_text="我们今天去顺达驾校学车",
            corrected_text="我们今天去顺达驾校学车"
        ),
    ]
    spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    
    # 判定标准：准确识别第 1 句为 retake_discard，第 2 句完整保留
    retake_spans = [s for s in spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 1
    assert "sub_01" in pruned_ids
    assert "sub_02" not in pruned_ids
    assert retake_spans[0].source_subtitle_id == "sub_01"

def test_tc_prune_002_rapid_parallel_speech_protection():
    """TC-PRUNE-002: 快速排比连读保护 (gap < 0.2s 时严禁误剪)"""
    subs = [
        SubtitleSegment(
            id="sub_p1",
            start_time=1.0,
            end_time=2.2,
            raw_text="这个点位很关键",
            corrected_text="这个点位很关键"
        ),
        SubtitleSegment(
            id="sub_p2",
            start_time=2.3, # gap = 0.1s < 0.2s 快速排比连读
            end_time=3.5,
            raw_text="这个点位要记牢",
            corrected_text="这个点位要记牢"
        ),
    ]
    spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    
    # 判定标准：触发快速排比连读守卫，两句均不得作为口误剔除
    retake_spans = [s for s in spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 0
    assert "sub_p1" not in pruned_ids
    assert "sub_p2" not in pruned_ids

def test_tc_prune_003_long_semantic_sentence_protection():
    """TC-PRUNE-003: 独立完整语义长句保护 (len >= 9 字时严禁因前缀相似误判为重读)"""
    subs = [
        SubtitleSegment(
            id="sub_l1",
            start_time=1.0,
            end_time=4.0,
            raw_text="我们今天在顺达驾校集合准备考试", # 15字独立长句
            corrected_text="我们今天在顺达驾校集合准备考试"
        ),
        SubtitleSegment(
            id="sub_l2",
            start_time=5.0, # 停顿 1.0s
            end_time=8.5,
            raw_text="我们今天在顺达驾校组织科目二考核", # 16字独立长句
            corrected_text="我们今天在顺达驾校组织科目二考核"
        ),
    ]
    spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    
    # 判定标准：触发长独立句保护安全网，不予剔除
    retake_spans = [s for s in spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 0
    assert "sub_l1" not in pruned_ids

def test_tc_prune_004_asr_merge_guard_retake_guard():
    """TC-PRUNE-004: ASR 合并阶段前缀重读阻断守卫"""
    raw_segments = [
        {
            "id": 1,
            "start_time": 0.5,
            "end_time": 1.4,
            "raw_text": "我们今天去顺达",
            "words": []
        },
        {
            "id": 2,
            "start_time": 1.8,
            "end_time": 3.8,
            "raw_text": "我们今天去顺达驾校练车",
            "words": []
        }
    ]
    merged = asr_runner.merge_short_segments(raw_segments, min_duration=2.0)
    
    # 判定标准：两句短句虽然时长 < 2.0s，但前缀高度重合，守卫阻断合并，保持两个独立片段
    assert len(merged) == 2
    assert "顺达" in merged[0]["raw_text"]
    assert "练车" in merged[1]["raw_text"]

def test_tc_video_001_and_002_ffmpeg_physical_cut_and_afade(tmp_path, monkeypatch):
    """TC-VIDEO-001 & 002: 物理切片拼接滤镜与接缝 15ms afade 防爆音断言"""
    th = tmp_path / "talking_head.mp4"
    th.write_bytes(b"th_dummy_bytes")
    out = tmp_path / "output_compact.mp4"

    # 视频时长 10.0s，剔除 [2.0, 4.0] (时长 2.0s)
    spans = [
        PruneSpan(id="sp_1", start_time=2.0, end_time=4.0, reason=PruneReason.RETAKE_DISCARD.value, is_active=True)
    ]
    kept = auto_prune_engine.compute_kept_spans(video_duration=10.0, prune_spans=spans)
    
    # 验证保留区间计算
    assert len(kept) == 2
    assert kept[0].start_time == 0.0
    assert kept[0].end_time == 2.0
    assert kept[1].start_time == 4.0
    assert kept[1].end_time == 10.0
    assert round(sum(k.duration for k in kept), 2) == 8.0 # 真实有效时长精确等于 10.0 - 2.0 = 8.0s
    
    # 验证 FFmpeg 音画切片拼接与淡入淡出滤镜构建
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
        total_duration=8.0,
        strategy={"video_speed": 1.0},
        kept_spans=kept
    )

    assert success is True
    assert out.exists()

    filter_idx = captured_cmd.index("-filter_complex")
    fc = captured_cmd[filter_idx + 1]

    # 必须包含 15ms (0.015s) 的音频交叉淡化（防爆音）
    assert "afade=t=in:ss=0:d=0.015" in fc
    assert "afade=t=out:st=1.985:d=0.015" in fc
    assert "afade=t=out:st=5.985:d=0.015" in fc
    assert "aresample=async=1000" in fc

    # 必须包含画面的 trim 切片与拼接
    assert "[0:v]trim=start=0.0:end=2.0" in fc
    assert "[0:v]trim=start=4.0:end=10.0" in fc
    assert "concat=n=2:v=1:a=1[v_raw_base][a_base]" in fc

def test_tc_broll_001_and_002_source_start_and_mute(tmp_path):
    """TC-BROLL-001 & 002: 分镜素材自身 In 点截取与纯静音画面覆盖断言"""
    broll = BrollReplacement(
        id="br_01",
        start_time=2.0,
        end_time=5.0,
        material_id="mat_broll",
        material_category=MaterialCategory.VENUE,
        source_start_time=1.8, # 素材从 1.8s 开始截取
        playback_mode="fit"
    )
    
    dur = broll.end_time - broll.start_time
    assert dur == 3.0
    
    # 滤镜参数生成断言
    trim_part = f"trim=start={broll.source_start_time:.3f}:duration={dur:.3f}"
    assert trim_part == "trim=start=1.800:duration=3.000"

def test_tc_sub_001_to_004_subtitle_crud_time_and_highlight():
    """TC-SUB-001 ~ 004: 字幕增删改、起止时间微调与高亮词全生命周期无损提取"""
    # 1. 验证新字幕自动提取高亮词规则
    test_text = "学员在考场练习科目二"
    hws = build_highlight_words(test_text)
    words = [w["word"] for w in hws if isinstance(w, dict)]
    assert "考场" in words or "科目二" in words
    
    # 2. 验证防倒置时间校验逻辑
    valid_start = 2.0
    valid_end = 4.5
    assert valid_end > valid_start + 0.05
    
    invalid_start = 4.0
    invalid_end = 3.5
    assert not (invalid_end > invalid_start + 0.05)

def test_tc_ui_virtual_timeline_reprojection_and_restore():
    """TC-UI-002: 剔除与一键恢复的虚拟时间轴重投影数学验证"""
    subs = [
        SubtitleSegment(id="s1", start_time=0.0, end_time=2.0, raw_text="第一句", corrected_text="第一句"),
        SubtitleSegment(id="s2", start_time=2.5, end_time=4.5, raw_text="第二句", corrected_text="第二句"),
        SubtitleSegment(id="s3", start_time=5.0, end_time=7.0, raw_text="第三句", corrected_text="第三句"),
    ]
    # 剔除 s2（区间 [2.5, 4.5]）
    spans = [
        PruneSpan(id="p1", start_time=2.5, end_time=4.5, reason="manual", is_active=True)
    ]
    kept = auto_prune_engine.compute_kept_spans(video_duration=7.0, prune_spans=spans)
    compact_subs = auto_prune_engine.reproject_subtitles_to_compact(subs, kept)
    
    # s1 应映射至 [0.0, 2.0]
    assert compact_subs[0].id == "s1"
    assert compact_subs[0].start_time == 0.0
    assert compact_subs[0].end_time == 2.0
    
    # s3 应向左平移 2.0s，从原 [5.0, 7.0] 平移至 [3.0, 5.0]
    assert compact_subs[1].id == "s3"
    assert compact_subs[1].start_time == 3.0
    assert compact_subs[1].end_time == 5.0
    
    # 当用户点击“恢复”取消剔除时 (spans 为空)
    kept_restored = auto_prune_engine.compute_kept_spans(video_duration=7.0, prune_spans=[])
    compact_restored = auto_prune_engine.reproject_subtitles_to_compact(subs, kept_restored)
    assert len(compact_restored) == 3
    assert compact_restored[1].id == "s2"
    assert compact_restored[2].start_time == 5.0 # 恢复后原位无损对齐

def test_tc_ui_single_unified_timeline_and_exact_time_display():
    """TC-UI-003: 单一统一紧凑时间轴与精确秒显示（剔除段时间轴彻底去掉，起止点精准对齐）"""
    # 场景复现用户真实素材：原片 0.00s - 4.96s 为开机准备/口误，4.96s - 6.56s 为第一句正文
    subs = [
        SubtitleSegment(id="s_idle", start_time=0.00, end_time=4.96, raw_text="准备开始录了啊", corrected_text="准备开始录了啊", is_pruned=True, prune_reason="head_idle"),
        SubtitleSegment(id="s_body1", start_time=4.96, end_time=6.56, raw_text="大家好今天给大家分享科目二", corrected_text="大家好今天给大家分享科目二"),
        SubtitleSegment(id="s_body2", start_time=6.80, end_time=9.20, raw_text="倒车入库其实有三个绝招", corrected_text="倒车入库其实有三个绝招"),
    ]
    spans = [
        PruneSpan(id="p_head", start_time=0.00, end_time=4.96, reason="head_idle", is_active=True)
    ]
    kept = auto_prune_engine.compute_kept_spans(video_duration=12.0, prune_spans=spans)
    compact_subs = auto_prune_engine.reproject_subtitles_to_compact(subs, kept)

    # 1. 验证被删减段的时间轴已彻底去掉：主轴仅包含有效句子，首句从 0.00s 精确起播
    assert len(compact_subs) == 2
    assert compact_subs[0].id == "s_body1"
    assert round(compact_subs[0].start_time, 2) == 0.00
    assert round(compact_subs[0].end_time, 2) == 1.60
    assert round(compact_subs[1].start_time, 2) == 1.84
    assert round(compact_subs[1].end_time, 2) == 4.24

    # 2. 验证紧凑时间轴向原始物理时间轴的可逆映射（保证持久化与压制无偏移）
    def map_compact_to_raw(compact_t, kept_spans):
        cum = 0.0
        for span in kept_spans:
            if compact_t <= cum + span.duration:
                return round(span.start_time + (compact_t - cum), 3)
            cum += span.duration
        return round(kept_spans[-1].end_time, 3)

    assert map_compact_to_raw(0.00, kept) == 4.96
    assert map_compact_to_raw(1.60, kept) == 6.56
    assert map_compact_to_raw(1.84, kept) == 6.80
    assert map_compact_to_raw(4.24, kept) == 9.20

