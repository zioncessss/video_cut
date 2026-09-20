import pytest
from app.native_engine.prune_engine import auto_prune_engine, AutoPruneEngine
from app.models.entities import SubtitleSegment, PruneReason, PruneSpan, KeptSpan

def test_head_tail_idle_prune():
    """测试首尾准备与关机废动作裁剪，验证安全气口保留"""
    # 模拟素材总长 30.0 秒
    # 首句从 3.5 秒才开始（头部有 3.5 秒准备期）
    # 末句在 27.0 秒结束（尾部有 3.0 秒关机期）
    subs = [
        SubtitleSegment(id="s1", start_time=3.5, end_time=6.0, raw_text="今天讲倒车入库", corrected_text="今天讲倒车入库"),
        SubtitleSegment(id="s2", start_time=6.3, end_time=10.0, raw_text="先看右后视镜", corrected_text="先看右后视镜"),
        SubtitleSegment(id="s3", start_time=24.0, end_time=27.0, raw_text="欢迎关注我们下期再见", corrected_text="欢迎关注我们下期再见")
    ]
    duration = 30.0

    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=duration,
        config={
            "head_padding_seconds": 0.20,
            "tail_padding_seconds": 0.25,
            "enable_retake_prune": False,
            "enable_mid_silence_prune": False
        }
    )

    # 验证头部裁剪: 0.0s 至 (3.5 - 0.20) = 3.30s
    assert len(prune_spans) == 2
    head_span = prune_spans[0]
    assert head_span.reason == PruneReason.HEAD_IDLE.value
    assert head_span.start_time == 0.0
    assert abs(head_span.end_time - 3.30) < 0.01

    # 验证尾部裁剪: (27.0 + 0.25) = 27.25s 至 30.0s
    tail_span = prune_spans[1]
    assert tail_span.reason == PruneReason.TAIL_IDLE.value
    assert abs(tail_span.start_time - 27.25) < 0.01
    assert tail_span.end_time == 30.0

def test_retake_detection_drop_earlier():
    """测试口误重说：典型案例《湖州驾校大改革》第0句与第1句（未加主语，停顿后重新完整说）"""
    subs = [
        # [0] 0.80s - 2.24s: 从今年九月份开始啊
        SubtitleSegment(id="sub_0", start_time=0.80, end_time=2.24, raw_text="从今年九月份开始啊", corrected_text="从今年九月份开始啊"),
        # [1] 2.76s - 5.10s: 湖州驾校从今年九月份开始 (停顿 0.52s)
        SubtitleSegment(id="sub_1", start_time=2.76, end_time=5.10, raw_text="湖州驾校从今年九月份开始", corrected_text="湖州驾校从今年九月份开始"),
        # [2] 5.30s - 7.50s: 我们现在学车通通一口价
        SubtitleSegment(id="sub_2", start_time=5.30, end_time=7.50, raw_text="我们现在学车通通一口价", corrected_text="我们现在学车通通一口价")
    ]
    duration = 10.0

    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=duration,
        config={
            "enable_head_prune": False,
            "enable_tail_prune": False,
            "enable_retake_prune": True,
            "retake_pause_min": 0.40,
            "retake_similarity_min": 0.60
        }
    )

    # 应识别出 sub_0 为口误重说弃用项
    assert "sub_0" in pruned_ids
    retake_spans = [s for s in prune_spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 1
    assert retake_spans[0].source_subtitle_id == "sub_0"
    assert retake_spans[0].target_subtitle_id == "sub_1"
    # 验证后置保留句前保留了起音安全缓冲
    assert retake_spans[0].start_time == 0.80

def test_mid_silence_compression_breath_gap():
    """测试中段看稿长停顿压缩：验证严格保留自然呼吸停顿（0.30s），绝不压成0毫秒"""
    subs = [
        SubtitleSegment(id="s1", start_time=1.0, end_time=3.0, raw_text="越承诺套路越深", corrected_text="越承诺套路越深"),
        # 停顿长达 3.0 秒 (3.0s -> 6.0s)
        SubtitleSegment(id="s2", start_time=6.0, end_time=8.5, raw_text="我前段时间还刷到一个套路", corrected_text="我前段时间还刷到一个套路")
    ]
    duration = 10.0

    prune_spans, _ = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=duration,
        config={
            "enable_head_prune": False,
            "enable_tail_prune": False,
            "enable_retake_prune": False,
            "enable_mid_silence_prune": True,
            "mid_silence_threshold": 1.20,
            "mid_silence_breath_gap": 0.30  # 两端各留 0.15s
        }
    )

    silence_spans = [s for s in prune_spans if s.reason == PruneReason.MID_SILENCE.value]
    assert len(silence_spans) == 1
    # 原本 3.0s -> 6.0s
    # 剪切点: (3.0 + 0.15) = 3.15s 到 (6.0 - 0.15) = 5.85s
    # 剪掉 2.70s，净保留 (3.15 - 3.0) + (6.0 - 5.85) = 0.30s 自然换气间隔！
    assert abs(silence_spans[0].start_time - 3.15) < 0.01
    assert abs(silence_spans[0].end_time - 5.85) < 0.01
    assert abs(silence_spans[0].duration - 2.70) < 0.01

def test_rhetorical_repetition_guard():
    """测试排比修辞防误杀：语流连贯、无口误卡壳停顿的连读强调不应被剔除"""
    subs = [
        SubtitleSegment(id="s1", start_time=1.0, end_time=2.0, raw_text="看这里", corrected_text="看这里"),
        # 紧凑连读，停顿仅 0.1 秒
        SubtitleSegment(id="s2", start_time=2.1, end_time=3.1, raw_text="看这里", corrected_text="看这里")
    ]
    duration = 5.0

    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=duration,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    # 排除误杀
    retake_spans = [s for s in prune_spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 0
    assert len(pruned_ids) == 0

def test_compute_kept_spans():
    """测试保留时间块反向计算"""
    prune_spans = [
        PruneSpan(start_time=0.0, end_time=2.0, reason=PruneReason.HEAD_IDLE.value),
        PruneSpan(start_time=10.0, end_time=13.0, reason=PruneReason.MID_SILENCE.value),
        PruneSpan(start_time=28.0, end_time=30.0, reason=PruneReason.TAIL_IDLE.value)
    ]
    video_dur = 30.0

    kept = auto_prune_engine.compute_kept_spans(video_dur, prune_spans)
    assert len(kept) == 2
    # 块 1: 2.0s -> 10.0s
    assert kept[0].start_time == 2.0
    assert kept[0].end_time == 10.0
    assert kept[0].duration == 8.0
    # 块 2: 13.0s -> 28.0s
    assert kept[1].start_time == 13.0
    assert kept[1].end_time == 28.0
    assert kept[1].duration == 15.0
