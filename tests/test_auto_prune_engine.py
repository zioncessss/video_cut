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

def test_reproject_subtitles_to_compact():
    """测试字幕紧凑时间轴重投影，包括词级时间戳毫秒级位移"""
    from app.models.entities import SubtitleWord
    subs = [
        SubtitleSegment(
            id="s1",
            start_time=2.76,
            end_time=4.88,
            raw_text="湖州驾校从今年九月份开始",
            corrected_text="湖州驾校从今年九月份开始",
            words=[
                SubtitleWord(word="湖州", start=2.76, end=3.10),
                SubtitleWord(word="驾校", start=3.10, end=3.50)
            ]
        ),
        SubtitleSegment(
            id="s2",
            start_time=22.02,
            end_time=24.50,
            raw_text="我来点个红心加关注",
            corrected_text="我来点个红心加关注",
            is_pruned=True,
            prune_reason="retake_discard"
        ),
        SubtitleSegment(
            id="s3",
            start_time=24.60,
            end_time=26.39,
            raw_text="评论区找我聊一下吧",
            corrected_text="评论区找我聊一下吧",
            words=[
                SubtitleWord(word="评论区", start=24.60, end=25.20)
            ]
        )
    ]
    # 模拟 kept_spans: [2.56, 21.84] (长度 19.28s) 与 [24.50, 26.50] (长度 2.0s)
    kept = [
        KeptSpan(start_time=2.56, end_time=21.84, duration=19.28),
        KeptSpan(start_time=24.50, end_time=26.50, duration=2.00)
    ]

    compact_subs = auto_prune_engine.reproject_subtitles_to_compact(subs, kept)
    assert len(compact_subs) == 2  # s2 被过滤
    assert compact_subs[0].id == "s1"
    # 原 2.76 - 2.56 = 0.20
    assert abs(compact_subs[0].start_time - 0.20) < 0.01
    assert abs(compact_subs[0].end_time - 2.32) < 0.01
    assert abs(compact_subs[0].words[0].start - 0.20) < 0.01

    # s3 处于第二块: 紧凑起点 19.28 + (24.60 - 24.50) = 19.38
    assert compact_subs[1].id == "s3"
    assert abs(compact_subs[1].start_time - 19.38) < 0.01

def test_retake_reverse_fluency_prefers_earlier_fluent_sentence():
    """测试流利度优选：后句严重卡壳停顿（>0.6s）时，逆转留后弃前，保留前驱流利原句"""
    from app.models.entities import SubtitleWord
    subs = [
        # 前句：流利无停顿（1.22s）
        SubtitleSegment(
            id="sub_prev",
            start_time=20.62,
            end_time=21.84,
            raw_text="点个红心加关注",
            corrected_text="点个红心加关注",
            words=[
                SubtitleWord(word="点", start=20.62, end=20.80),
                SubtitleWord(word="个", start=20.80, end=20.95),
                SubtitleWord(word="红心", start=20.95, end=21.35),
                SubtitleWord(word="加关注", start=21.35, end=21.84)
            ]
        ),
        # 后句：死寂卡壳自言自语（句内停顿长达 1.16 秒）
        SubtitleSegment(
            id="sub_next",
            start_time=22.02,
            end_time=24.50,
            raw_text="我来点个红心加关注",
            corrected_text="我来点个红心加关注",
            words=[
                SubtitleWord(word="我", start=22.02, end=22.15),
                SubtitleWord(word="来", start=22.15, end=22.28),
                # 停顿: 23.44 - 22.28 = 1.16 秒死寂！
                SubtitleWord(word="点", start=23.44, end=23.60),
                SubtitleWord(word="个", start=23.60, end=23.75),
                SubtitleWord(word="红心", start=23.75, end=24.15),
                SubtitleWord(word="加关注", start=24.15, end=24.50)
            ]
        )
    ]
    duration = 27.0
    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=duration,
        config={
            "enable_head_prune": False,
            "enable_tail_prune": False,
            "enable_retake_prune": True,
            "retake_pause_min": 0.18,
            "retake_similarity_min": 0.60
        }
    )

    # 关键断言：必须剔除卡壳后句 sub_next，保留流畅前句 sub_prev！
    assert "sub_next" in pruned_ids
    assert "sub_prev" not in pruned_ids
    retake_spans = [s for s in prune_spans if s.reason == PruneReason.RETAKE_DISCARD.value]
    assert len(retake_spans) == 1
    assert retake_spans[0].source_subtitle_id == "sub_next"
    assert retake_spans[0].target_subtitle_id == "sub_prev"

