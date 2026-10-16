import pytest
from app.native_engine.prune_engine import auto_prune_engine
from app.models.entities import SubtitleSegment

def test_prune_retake_short_prefix():
    # 模拟口播典型口误：短前缀说错重读
    # 前句："顺达" (2字)，停顿 0.45s，后句："顺达驾校自建五万平训练场"
    subs = [
        SubtitleSegment(
            id="sub_1",
            start_time=1.0,
            end_time=1.8,
            raw_text="顺达",
            corrected_text="顺达"
        ),
        SubtitleSegment(
            id="sub_2",
            start_time=2.25, # gap = 0.45s
            end_time=5.5,
            raw_text="顺达驾校自建五万平训练场",
            corrected_text="顺达驾校自建五万平训练场"
        )
    ]
    
    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    
    assert "sub_1" in pruned_ids, "口误短前缀 '顺达' 应被精准识别并剔除"
    retake_spans = [s for s in prune_spans if s.reason == "retake_discard"]
    assert len(retake_spans) == 1
    assert retake_spans[0].source_subtitle_id == "sub_1"

def test_prune_retake_fuzzy_prefix_stumble():
    # 模拟口误读错一个字后重录：前句 "我们学车呢"，后句 "我们学车一定要找正规驾校"
    subs = [
        SubtitleSegment(
            id="sub_1",
            start_time=1.0,
            end_time=2.2,
            raw_text="我们学车呢",
            corrected_text="我们学车呢"
        ),
        SubtitleSegment(
            id="sub_2",
            start_time=2.65, # gap = 0.45s
            end_time=6.0,
            raw_text="我们学车一定要找正规驾校",
            corrected_text="我们学车一定要找正规驾校"
        )
    ]
    
    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True, "retake_pause_min": 0.40}
    )
    
    assert "sub_1" in pruned_ids, "口误读错短句 '我们学车呢' 前缀重叠度高，应被判定为重读剔除"

def test_prune_retake_safety_guards_rhetorical():
    # 安全网测试 1：快速排比连读（gap < 0.20s）绝不误剪
    subs = [
        SubtitleSegment(
            id="sub_1",
            start_time=1.0,
            end_time=1.5,
            raw_text="学车",
            corrected_text="学车"
        ),
        SubtitleSegment(
            id="sub_2",
            start_time=1.62, # gap = 0.12s 极短排比连读
            end_time=2.2,
            raw_text="学车一定要找我们",
            corrected_text="学车一定要找我们"
        )
    ]
    
    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True}
    )
    
    assert "sub_1" not in pruned_ids, "快速排比连读不应被误剪"

def test_prune_retake_safety_guards_long_independent_sentence():
    # 安全网测试 2：长独立完整语义句（>=9字且非后句纯子串）绝不误剪
    subs = [
        SubtitleSegment(
            id="sub_1",
            start_time=1.0,
            end_time=4.0,
            raw_text="顺达驾校不仅有专业教练团队", # 13字完整语义
            corrected_text="顺达驾校不仅有专业教练团队"
        ),
        SubtitleSegment(
            id="sub_2",
            start_time=4.6, # gap = 0.6s
            end_time=8.0,
            raw_text="顺达驾校还提供全流程班车接送", # 相同前缀但均为独立长句
            corrected_text="顺达驾校还提供全流程班车接送"
        )
    ]
    
    prune_spans, pruned_ids = auto_prune_engine.analyze_and_prune(
        subtitles=subs,
        video_duration=10.0,
        config={"enable_retake_prune": True}
    )
    
    assert "sub_1" not in pruned_ids, "独立完整长句不应被误剪"
