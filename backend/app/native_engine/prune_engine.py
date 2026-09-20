import re
import difflib
from typing import List, Dict, Any, Tuple, Optional
from app.models.entities import PruneSpan, KeptSpan, PruneReason

def _clean_text(text: str) -> str:
    """清理标点符号与空白字符，提取核心字词"""
    if not text:
        return ""
    return re.sub(r"[^\w\u4e00-\u9fa5]", "", text).strip().lower()

def _longest_common_substring_len(s1: str, s2: str) -> int:
    """计算两个中文字符串的最长连续公共子串长度"""
    if not s1 or not s2:
        return 0
    m = [[0] * (1 + len(s2)) for _ in range(1 + len(s1))]
    longest = 0
    for x in range(1, 1 + len(s1)):
        for y in range(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
            else:
                m[x][y] = 0
    return longest

class AutoPruneEngine:
    """
    智能粗剪算法引擎：
    1. 自动检测首句前的开机准备动作（保留安全起音气口）
    2. 自动检测尾句后的关机废动作（保留自然收音气口）
    3. 智能检测口误重说与改口（基于停顿与字词重叠度，遵循“留后弃前”）
    4. 自动压缩中段无声长冷场（保留 0.3s~0.35s 人类自然舒适换气停顿）
    5. 计算音视频无缝拼合的有效保留时间块 (KeptSpans)
    """

    def __init__(self):
        pass

    def analyze_and_prune(
        self,
        subtitles: List[Any],
        video_duration: float,
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[PruneSpan], List[str]]:
        """
        核心粗剪分析函数：
        输入字幕条目列表（可以是 SubtitleSegment 或 dict）与素材总时长，
        输出: (prune_spans, pruned_subtitle_ids)
        """
        cfg = config or {}
        enable_head = cfg.get("enable_head_prune", True)
        enable_tail = cfg.get("enable_tail_prune", True)
        enable_retake = cfg.get("enable_retake_prune", True)
        enable_mid_silence = cfg.get("enable_mid_silence_prune", True)

        head_padding = float(cfg.get("head_padding_seconds", 0.20))
        tail_padding = float(cfg.get("tail_padding_seconds", 0.25))
        retake_pause_min = float(cfg.get("retake_pause_min", 0.40))
        retake_similarity_min = float(cfg.get("retake_similarity_min", 0.60))
        mid_silence_threshold = float(cfg.get("mid_silence_threshold", 1.20))
        mid_silence_breath_gap = float(cfg.get("mid_silence_breath_gap", 0.30))

        prune_spans: List[PruneSpan] = []
        pruned_sub_ids: List[str] = []

        if not subtitles or video_duration <= 0.1:
            return prune_spans, pruned_sub_ids

        # 辅助取值函数
        def _get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        n = len(subtitles)

        # 1. 头部废动作检测 (Head Idle)
        first_sub = subtitles[0]
        first_start = float(_get_val(first_sub, "start_time", 0.0))
        if enable_head and first_start > head_padding + 0.05:
            prune_end = round(max(0.0, first_start - head_padding), 3)
            if prune_end > 0.05:
                span = PruneSpan(
                    start_time=0.0,
                    end_time=prune_end,
                    reason=PruneReason.HEAD_IDLE.value,
                    duration=prune_end,
                    is_active=True
                )
                prune_spans.append(span)

        # 2. 口误重说检测 (Retake Detection - "舍弃前驱，保留后效")
        retake_marked_indices = set()
        if enable_retake and n >= 2:
            i = 0
            while i < n - 1:
                cur_sub = subtitles[i]
                next_sub = subtitles[i + 1]

                cur_text = _clean_text(_get_val(cur_sub, "corrected_text") or _get_val(cur_sub, "raw_text", ""))
                next_text = _clean_text(_get_val(next_sub, "corrected_text") or _get_val(next_sub, "raw_text", ""))
                
                cur_end = float(_get_val(cur_sub, "end_time", 0.0))
                next_start = float(_get_val(next_sub, "start_time", 0.0))
                gap = next_start - cur_end

                is_retake = False

                if cur_text and next_text:
                    # 规则 A: 相同词连说但停顿正常（排除紧凑修辞强调）
                    # 若完全相同或高度包含，且停顿大于等于 retake_pause_min
                    ratio = difflib.SequenceMatcher(None, cur_text, next_text).ratio()
                    lcs_len = _longest_common_substring_len(cur_text, next_text)
                    min_len = min(len(cur_text), len(next_text))
                    
                    # 包含关系（如: "从今年九月份开始啊" vs "湖州驾校从今年九月份开始", 或 "点个红心加关注" vs "我来点个红心加关注"）
                    is_substring_included = (cur_text in next_text) or (next_text in cur_text)
                    lcs_coverage = (lcs_len / min_len) if min_len > 0 else 0.0

                    # 判定条件：
                    # 1. 停顿属于口误卡壳区间 (gap >= retake_pause_min 且 gap <= 3.5s)
                    # 2. 文本重合度高 (ratio >= retake_similarity_min 或 lcs_coverage >= 0.7 且公共字数 >= 3)
                    if (gap >= retake_pause_min or (gap >= 0.15 and is_substring_included)) and gap <= 3.5:
                        if ratio >= retake_similarity_min or (lcs_coverage >= 0.70 and lcs_len >= 3):
                            # 防排比修辞：排比通常两句字数完全一致且语调短促 (gap < 0.25)
                            if not (cur_text == next_text and gap < 0.25):
                                is_retake = True

                if is_retake:
                    retake_marked_indices.add(i)
                    cur_id = _get_val(cur_sub, "id")
                    next_id = _get_val(next_sub, "id")
                    pruned_sub_ids.append(cur_id)

                    cur_start = float(_get_val(cur_sub, "start_time", 0.0))
                    # 剔除整个前置错误片段，在后置保留句前保留安全起音气口
                    prune_end = round(max(cur_end, next_start - head_padding), 3)
                    span = PruneSpan(
                        start_time=round(cur_start, 3),
                        end_time=prune_end,
                        reason=PruneReason.RETAKE_DISCARD.value,
                        source_subtitle_id=cur_id,
                        target_subtitle_id=next_id,
                        duration=round(prune_end - cur_start, 3),
                        is_active=True
                    )
                    prune_spans.append(span)
                i += 1

        # 3. 中段单纯长停顿气口压缩 (Mid-Silence Compression)
        if enable_mid_silence and n >= 2:
            half_breath = round(mid_silence_breath_gap / 2.0, 3)
            for i in range(n - 1):
                # 如果当前或下一句已被口误剔除，跳过中段单纯静音判断
                if i in retake_marked_indices or (i + 1) in retake_marked_indices:
                    continue

                cur_sub = subtitles[i]
                next_sub = subtitles[i + 1]

                cur_end = float(_get_val(cur_sub, "end_time", 0.0))
                next_start = float(_get_val(next_sub, "start_time", 0.0))
                gap = next_start - cur_end

                if gap > mid_silence_threshold:
                    # 中段静音压缩：绝不压成 0 秒，严格保留两端各 half_breath (合计 mid_silence_breath_gap) 的呼吸气口
                    cut_start = round(cur_end + half_breath, 3)
                    cut_end = round(next_start - half_breath, 3)
                    if cut_end > cut_start + 0.1:
                        span = PruneSpan(
                            start_time=cut_start,
                            end_time=cut_end,
                            reason=PruneReason.MID_SILENCE.value,
                            duration=round(cut_end - cut_start, 3),
                            is_active=True
                        )
                        prune_spans.append(span)

        # 4. 尾部废动作检测 (Tail Idle)
        last_sub = subtitles[-1]
        last_end = float(_get_val(last_sub, "end_time", 0.0))
        if enable_tail and (video_duration - last_end > tail_padding + 0.05):
            prune_start = round(last_end + tail_padding, 3)
            if prune_start < video_duration - 0.05:
                span = PruneSpan(
                    start_time=prune_start,
                    end_time=round(video_duration, 3),
                    reason=PruneReason.TAIL_IDLE.value,
                    duration=round(video_duration - prune_start, 3),
                    is_active=True
                )
                prune_spans.append(span)

        # 5. 区间合并与按时间排序
        merged_spans = self._merge_and_sort_spans(prune_spans)
        return merged_spans, pruned_sub_ids

    def _merge_and_sort_spans(self, spans: List[PruneSpan]) -> List[PruneSpan]:
        """合并重叠或微小相邻的剔除区间，保证单调递增无冲突"""
        if not spans:
            return []
        sorted_spans = sorted(spans, key=lambda s: s.start_time)
        merged: List[PruneSpan] = []

        for s in sorted_spans:
            if not merged:
                merged.append(s)
                continue
            prev = merged[-1]
            # 若两区间重叠或间隙小于 0.05 秒，合并
            if s.start_time <= prev.end_time + 0.05:
                new_end = max(prev.end_time, s.end_time)
                prev.end_time = round(new_end, 3)
                prev.duration = round(prev.end_time - prev.start_time, 3)
                # 若合并项包含口误重说，保留重说原因标识
                if s.reason == PruneReason.RETAKE_DISCARD.value:
                    prev.reason = s.reason
                    prev.source_subtitle_id = s.source_subtitle_id
                    prev.target_subtitle_id = s.target_subtitle_id
            else:
                merged.append(s)

        return merged

    def compute_kept_spans(
        self,
        video_duration: float,
        prune_spans: List[PruneSpan]
    ) -> List[KeptSpan]:
        """
        反向计算最终有效发音/画面的保留时间区间 (KeptSpans)。
        用于驱动前端虚拟跳播映射与 FFmpeg 多切片无损拼接。
        """
        if video_duration <= 0:
            return []

        active_spans = [s for s in (prune_spans or []) if getattr(s, 'is_active', True)]
        merged_prunes = self._merge_and_sort_spans(active_spans)

        kept: List[KeptSpan] = []
        cur_pos = 0.0

        for ps in merged_prunes:
            p_start = max(0.0, ps.start_time)
            p_end = min(video_duration, ps.end_time)

            if p_start > cur_pos + 0.05:
                kept.append(KeptSpan(
                    start_time=round(cur_pos, 3),
                    end_time=round(p_start, 3),
                    duration=round(p_start - cur_pos, 3),
                    audio_fade=True
                ))
            cur_pos = max(cur_pos, p_end)

        if cur_pos < video_duration - 0.05:
            kept.append(KeptSpan(
                start_time=round(cur_pos, 3),
                end_time=round(video_duration, 3),
                duration=round(video_duration - cur_pos, 3),
                audio_fade=True
            ))

        return kept

    def map_interval_to_compact(
        self,
        orig_start: float,
        orig_end: float,
        kept_spans: List[KeptSpan]
    ) -> Optional[Tuple[float, float]]:
        """将原始时间戳区间映射到剔除后的紧凑时间轴，若全部落在剔除段则返回 None"""
        if not kept_spans:
            return None

        cum_time = 0.0
        mapped_start = None
        mapped_end = None

        for span in kept_spans:
            s_start = span.start_time
            s_end = span.end_time
            dur = span.duration

            # 检查相交
            if orig_start < s_end and orig_end > s_start:
                eff_start = max(orig_start, s_start)
                eff_end = min(orig_end, s_end)
                local_start = cum_time + (eff_start - s_start)
                local_end = cum_time + (eff_end - s_start)
                if mapped_start is None or local_start < mapped_start:
                    mapped_start = local_start
                if mapped_end is None or local_end > mapped_end:
                    mapped_end = local_end

            cum_time += dur

        if mapped_start is not None and mapped_end is not None and mapped_end > mapped_start:
            return round(mapped_start, 3), round(mapped_end, 3)
        return None

auto_prune_engine = AutoPruneEngine()
