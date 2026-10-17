import subprocess
import json
import os
import time
import threading
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
import re

_asr_concurrency_lock = threading.BoundedSemaphore(2)
INSEPARABLE_WORDS = {
    # 短视频互动导流与CTA核心词（杜绝如"想要了/解"、"评论区/留言"被拆散）
    "了解", "想要了解", "评论区", "留言", "评论区留言", "私信", "咨询", "关注", "点赞", "收藏", "联系",
    "为了", "除了", "明白", "清楚", "记得", "不仅是", "不仅有",
    # 驾考专有科目与操作
    "科目一", "科目二", "科目三", "科目四", "科一", "科二", "科三", "科四",
    "倒车入库", "侧方停车", "半坡起步", "曲线行驶", "直角转弯", "坡道起步",
    "后视镜", "反光镜", "转向灯", "安全带", "离合器", "离合", "刹车", "手刹", "油门",
    "方向盘", "挡位", "一挡", "二挡", "倒挡", "空挡", "自动挡", "手动挡",
    "控制线", "打死", "回正", "点位", "看点", "压线", "打左转向灯", "打右转向灯", "鸣笛",
    "训练场", "练车", "考场", "模拟机", "遮阳大棚", "空调", "冷暖空调", "打转向灯",
    "自动挡模拟机",
    # 费用与模式
    "全包班", "基础班", "直通班", "快班",
    "模拟费", "补考费", "加急费", "体检费", "工本费", "打证费", "学时费", "额外费用", "隐形消费", "乱收费",
    "吃拿卡要", "随到随学", "一对一", "手把手", "包过", "拿证", "领证", "收费模式",
    "一次性", "中途", "前期", "后期", "合同", "退费", "两千八百八十元",
    # 常用口语高频词与搭配
    "咱们", "我们", "你们", "他们", "大家", "可以", "这种", "三种", "很多",
    "之前", "之后", "一直", "答应", "体验", "下降", "上升", "后续", "套路", "承诺",
    "外地", "本地", "外地学员", "本地学员", "考试", "比较", "时间", "而且", "如果",
    "首先", "靠谱", "不妨", "红心", "做了", "服务", "滴滴", "一下", "学车",
    "驾校", "教练", "学员", "踩坑", "避雷", "便宜", "报名", "怎么样", "收费",
    "现在", "找到", "觉得", "合适", "原因", "什么", "知道", "看到", "听到",
    "比如", "还有", "另外", "特别是", "可以说", "也就是", "百分之百", "离谱", "正常",
    "两三个月", "一个", "一种", "总担心", "担心", "害怕", "紧张", "零基础",
    "通过率", "合格率", "抓紧了", "抓紧", "回家过年", "下个月", "下周", "练车时间",
    "省心省力", "感受到", "感受", "明显", "抖动", "慢抬", "慢松", "稳住", "切记",
    "而且还有", "所有的", "全部包含", "包含在内", "自由预约", "免费练习",
    "的时候", "的人", "练车的人"
}

CLAUSE_STARTERS = (
    # 序号引导
    "第一", "第二", "第三", "第四", "首先", "其次", "最后",
    # 强转折与递进连词
    "但是", "可是", "不过", "然而", "而且还有", "而且", "并且还有", "并且",
    "然后", "如果", "因为", "所以", "或者", "另外", "特别是", "尤其是",
    "甚至", "不如", "其实咱们", "其实", "哪怕", "只要", "只要你", "不仅有", "不仅",
    # 范围与介词短语引导
    "从科目一", "从科一", "从", "在", "为了", "关于",
    # 人称与呼吁
    "咱们", "我们", "你们", "他们", "大家", "不妨在", "不妨", "建议", "切记",
    # 动作与重点引导
    "一定要", "千万要", "千万", "手把手", "可以", "不用", "绝不", "直接", "不需要",
    "现在报名", "现在", "下周就能", "下周", "下个月直接", "下个月",
    "上车先", "调整后视镜", "踩离合", "看后视镜", "鸣笛", "松手刹", "打左转向灯", "打右转向灯",
    "可以说", "也就是", "也就是说", "真的没有", "真的", "等你", "你会", "他是", "他就",
    "收费特别多", "全部包含在内"
)

# 未完句尾禁绝库：连词、介词、开放性弱动词与从属修饰语（彻底杜绝"我们都有老师和"或"想要了/解"挂尾）
INCOMPLETE_TAIL_WORDS = (
    # 弱连词
    "和", "与", "跟", "及", "同", "并且", "而且", "或者", "还是", "甚至", "但", "但是", "因为", "所以", "如果",
    # 介词
    "在", "从", "由", "把", "被", "让", "到", "向",
    # 悬挂动词与弱从属限定语
    "来", "去", "给", "找", "所有的", "全部的"
)

SAFE_TAIL_EXCEPTIONS = {
    "向": ("方向", "反向", "正向", "导向", "走向"),
    "到": ("看到", "听到", "遇到", "学到", "拿到", "周到", "办到", "做到", "找到", "感到", "随到随学", "领到", "报到")
}

CLAUSE_ENDERS = (
    "呢", "吧", "啊", "吗", "呀", "啦", "哒", "哦", "哈", "了", "的", "过",
    "的时候", "之后", "之前", "以后", "以前", "当时",
    "抓紧了", "便宜", "怎么样", "靠谱吗", "很多", "回家过年", "随到随学", "省心省力",
    "包含在内", "全部包含", "额外费用", "隐形消费", "乱收费", "大棚", "后视镜",
    "安全带", "起步", "打死", "回正", "慢抬", "慢松刹车", "手刹", "练车", "拿证",
    "吃拿卡要", "避雷", "免费练习", "特别多", "两千八百八十元", "学车"
)

PUNCTUATION_CHARS = set("，, 。. !！ ?？ ;； 、")


def is_breaking_inseparable_word(left_text: str, right_text: str) -> bool:
    """判定两段文本的接缝处是否正好腰斩了一个不可分词汇"""
    if not left_text or not right_text:
        return False
    l_tail = left_text[-10:]
    r_head = right_text[:10]
    for w in INSEPARABLE_WORDS:
        for cut in range(1, len(w)):
            prefix = w[:cut]
            suffix = w[cut:]
            if l_tail.endswith(prefix) and r_head.startswith(suffix):
                return True
    return False


def is_incomplete_tail(left_text: str) -> bool:
    """判定前半句结尾是否处于未完成语义断裂态（连词、介词或悬挂动词）"""
    if not left_text:
        return False
    for tail in INCOMPLETE_TAIL_WORDS:
        if left_text.endswith(tail):
            if tail in SAFE_TAIL_EXCEPTIONS:
                if any(left_text.endswith(exc) for exc in SAFE_TAIL_EXCEPTIONS[tail]):
                    continue
            return True
    return False


def find_best_split_point(
    words: List[Dict[str, Any]],
    min_chunk: int = 4,
    max_chars: int = 15,
    soft_max: int = 15
) -> int:
    total_len = sum(len(w.get("word", "")) for w in words)
    if total_len <= soft_max:
        return -1

    # 黄金阅读区间：口播短视频每行 8 ~ 13 字最佳，根据总字数自适应分段
    ideal_k = max(2, round(total_len / 11.5))
    ideal_left = max(min_chunk, min(max_chars, round(total_len / ideal_k)))

    best_idx = -1
    best_score = -999999.0

    curr_len = 0
    for i in range(len(words) - 1):
        curr_len += len(words[i].get("word", ""))
        rem_len = total_len - curr_len

        if curr_len < min_chunk or rem_len < min_chunk:
            continue

        left_text = "".join(w.get("word", "") for w in words[:i + 1])
        right_text = "".join(w.get("word", "") for w in words[i + 1:])

        # 绝对防线 1：严禁拆解专有名词与固定搭配（如"了解"、"科目二"）
        if is_breaking_inseparable_word(left_text, right_text):
            continue

        # 绝对防线 2：严禁未完句尾（弱连词/介词/悬挂动词如"和"、"在"、"来"）
        if is_incomplete_tail(left_text):
            continue

        w_curr = words[i]
        w_next = words[i + 1]
        gap = max(0.0, float(w_next.get("start", 0.0)) - float(w_curr.get("end", 0.0)))

        # 基础长度得分：越接近黄金目标字数得分越高
        score = 100.0 - 2.5 * abs(curr_len - ideal_left)

        # 黄金意群字数区间 [8, 13] 给予强力鼓励
        if 8 <= curr_len <= 13:
            score += 35.0
        elif 6 <= curr_len <= 14:
            score += 20.0
        elif curr_len <= max_chars:
            score += 10.0

        # 自然标点断句奖励（标点符号是最高优先级断句点）
        if any(p in w_curr.get("word", "") for p in PUNCTUATION_CHARS):
            score += 500.0

        # 语法意群前缀与句尾奖励
        if any(right_text.startswith(st) for st in CLAUSE_STARTERS):
            score += 70.0
        if any(left_text.endswith(ed) for ed in CLAUSE_ENDERS):
            score += 50.0

        # 声学停顿优先加分：短视频停顿 >= 0.25s 意味着极其明确的停顿断句点
        score += min(60.0, gap * 200.0)
        if gap >= 0.25:
            score += 40.0

        # 边界与超长约束
        if curr_len > max_chars:
            score -= 100.0 * (curr_len - max_chars)

        # 剩余长度规划：若剩余长度能够再次健康切分（>= 12），不进行严厉惩罚
        if rem_len <= soft_max:
            score += 25.0
        elif rem_len >= min_chunk * 2:
            score += 15.0
        else:
            score -= 20.0 * (rem_len - soft_max)

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx


def split_words_to_safe_chunks(
    words: List[Dict[str, Any]],
    min_chunk: int = 4,
    max_chars: int = 15,
    soft_max: int = 15
) -> List[List[Dict[str, Any]]]:
    total_len = sum(len(w.get("word", "")) for w in words)
    if total_len <= soft_max:
        return [words]

    idx = find_best_split_point(words, min_chunk=min_chunk, max_chars=max_chars, soft_max=soft_max)
    if idx == -1:
        idx = find_best_split_point(words, min_chunk=2, max_chars=max_chars, soft_max=soft_max)
        if idx == -1:
            # 兜底硬保 max_chars 安全防线，避免折行
            curr_acc = 0
            best_fallback_idx = 0
            for wi, w in enumerate(words):
                curr_acc += len(w.get("word", ""))
                if curr_acc <= max_chars:
                    best_fallback_idx = wi
                else:
                    break
            idx = max(0, best_fallback_idx)

    left_words = words[:idx + 1]
    right_words = words[idx + 1:]
    return (
        split_words_to_safe_chunks(left_words, min_chunk, max_chars, soft_max) +
        split_words_to_safe_chunks(right_words, min_chunk, max_chars, soft_max)
    )


class ASRRunner:
    def __init__(self):
        self._model = None

    def extract_audio(self, video_path: Path, output_audio_path: Path) -> bool:
        """从视频中抽取 16kHz 单声道 wav 音频以供 ASR 识别"""
        from app.core.config import get_ffmpeg_cmd
        ffmpeg_bin = get_ffmpeg_cmd()
        try:
            cmd = [
                ffmpeg_bin, "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(output_audio_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if res.returncode != 0:
                err_str = res.stderr.decode("utf-8", errors="replace")
                print(f"[ASRRunner] FFmpeg 抽取音频失败 (exit {res.returncode}): {err_str[-300:]}")
                return False
            return output_audio_path.exists() and output_audio_path.stat().st_size > 0
        except Exception as e:
            print(f"[ASRRunner] Audio extraction exception: {e}")
            return False

    FILLER_PATTERN = re.compile(r'^[呃额嗯唔啊诶哎呀喔噢]+[，。？！…\s]*$|^[eE][hH]|[uU][mM]|[aA][hH]$')
    FILLER_LEADING_CHARS = set("呃额嗯唔啊诶哎嗷")
    FILLER_LEADING_WORDS = ("那个", "就是说")
    QUESTION_WORDS = ("什么", "怎么", "哪", "谁", "几", "为何", "如何", "吗", "?", "？")

    def filter_filler_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        过滤纯语气填充词与无意义口癖占位符（如 '呃'、'额'、'嗯'、'唔' 等独立微短片段），
        彻底杜绝其成为独立字幕卡片或产生无意义分镜占位。
        """
        cleaned: List[Dict[str, Any]] = []
        for s in segments:
            text = (s.get("corrected_text") or s.get("raw_text") or "").strip()
            dur = s.get("end_time", 0.0) - s.get("start_time", 0.0)
            if self.FILLER_PATTERN.match(text) and (dur < 0.8 or len(text) <= 2):
                continue
            cleaned.append(s)
        return cleaned

    def clean_filler_particles(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        精细清洗字幕中的语气停顿词与无意义口癖：
        1. 清洗句首语气词（呃、啊、额、嗯、唔、那个等），去除多余停顿感；
        2. 清洗句末无疑问语气的口癖拖音助词（如'从科一到科四呢'中的'呢'）；
        3. 同步裁剪逐字时间戳 words 列表，使物理起止时间与新文本严格对齐。
        """
        cleaned_list: List[Dict[str, Any]] = []
        for s in segments:
            seg = dict(s)
            text = (seg.get("corrected_text") or seg.get("raw_text") or "").strip()
            words = list(seg.get("words") or [])

            # 1. 过滤句首语气词
            changed = True
            while changed and text:
                changed = False
                if text[0] in self.FILLER_LEADING_CHARS:
                    if len(text) == 1 or text[1] in "，, 、" or text[0] in "呃额嗯唔":
                        text = text[1:].lstrip("，, 、")
                        if words:
                            words = words[1:]
                        changed = True
                        continue
                for fl_word in self.FILLER_LEADING_WORDS:
                    if text.startswith(fl_word) and len(text) > len(fl_word) + 2:
                        text = text[len(fl_word):].lstrip("，, 、")
                        if words and len(words) >= len(fl_word):
                            words = words[len(fl_word):]
                        changed = True
                        break

            # 2. 清洗句末非疑问语气的拖尾口癖（如"从科一到科四呢" -> "从科一到科四"）
            if text.endswith("呢") and not any(qw in text for qw in self.QUESTION_WORDS):
                text = text[:-1].rstrip("，, ")
                if words and words[-1].get("word") == "呢":
                    words = words[:-1]

            if not text:
                continue

            seg["corrected_text"] = text
            seg["raw_text"] = text
            if words:
                seg["words"] = words
                seg["start_time"] = round(float(words[0].get("start", seg.get("start_time", 0.0))), 3)
                seg["end_time"] = round(float(words[-1].get("end", seg.get("end_time", 0.0))), 3)

            cleaned_list.append(seg)
        return cleaned_list

    def split_into_readable_segments(
        self,
        segments: List[Dict[str, Any]],
        max_chars: int = 15,
        soft_max: Optional[int] = None,
        min_chunk: int = 4
    ) -> List[Dict[str, Any]]:
        """
        针对口播短视频进行 8~15 字自然意群与视读切分（单行优先，带防孤字、防碎尾与弹性意群保护）：
        1. 针对健康单行（<= soft_max，默认 15 字），不盲目硬拆，完整保留自然意群，实现画面尽量不换行；
        2. 若长句必须切分，执行严格的防孤字与杜绝连词挂尾保护：严禁剩余字数 < min_chunk (4字)，严禁以'和/与/在/从'挂尾；
        3. 优先在自然标点、完整半句谓词、声学停顿处切分；
        4. 切分后自动执行局部微短碎片吸附。
        """
        refined_segments = []
        import re

        if soft_max is None:
            soft_max = max(max_chars + 2, 18) if max_chars >= 18 else max_chars

        for seg in segments:
            text = (seg.get("corrected_text") or seg.get("raw_text", "")).strip()
            start = seg.get("start_time", 0.0)
            end = seg.get("end_time", start + 3.0)
            duration = max(0.2, end - start)
            words = seg.get("words") or []

            # 如果句子本身字数在弹性安全范围内，直接完整保留完整意群
            if len(text) <= soft_max:
                refined_segments.append(seg)
                continue

            # 方案 A：具备真实物理词时间戳（word_timestamps=True）
            if words and isinstance(words, list) and len(words) > 1:
                word_chunks = split_words_to_safe_chunks(words, min_chunk=min_chunk, max_chars=max_chars, soft_max=soft_max)
                for idx_c, c_words in enumerate(word_chunks):
                    w_text = "".join(x.get("word", "") for x in c_words).strip()
                    if not w_text:
                        continue
                    sub = dict(seg)
                    sub["id"] = f"{seg.get('id', 'seg')}_{len(refined_segments)}"
                    sub["start_time"] = round(float(c_words[0].get("start", start)), 3)
                    sub["end_time"] = round(float(c_words[-1].get("end", end)), 3)
                    sub["raw_text"] = w_text
                    sub["corrected_text"] = w_text
                    sub["words"] = list(c_words)
                    refined_segments.append(sub)
                continue

            # 方案 B：无词级时间戳，采用自然语法意群与标点智能切分
            raw_clauses = [c.strip() for c in re.split(r'[,，;；!！?？。、\s]+', text) if c.strip()]
            if not raw_clauses:
                raw_clauses = [text]

            total_clean_chars = sum(len(c) for c in raw_clauses)
            cur_clause_start = start

            for c_idx, clause in enumerate(raw_clauses):
                clause_dur = duration * (len(clause) / max(1, total_clean_chars))
                clause_end = end if c_idx == len(raw_clauses) - 1 else round(cur_clause_start + clause_dur, 3)

                if len(clause) <= soft_max:
                    sub_seg = dict(seg)
                    sub_seg["id"] = f"{seg.get('id', 'seg')}_{len(refined_segments)}"
                    sub_seg["start_time"] = round(cur_clause_start, 3)
                    sub_seg["end_time"] = round(clause_end, 3)
                    sub_seg["raw_text"] = clause
                    sub_seg["corrected_text"] = clause
                    refined_segments.append(sub_seg)
                else:
                    # 子分句超长，合成字符级词时间戳，统一复用不可分词与防连词挂尾保护的安全切分算法
                    clean_chars = list(clause)
                    dur_c = max(0.2, clause_end - cur_clause_start)
                    step = dur_c / max(1, len(clean_chars))
                    cur_t = cur_clause_start
                    synth_words = []
                    for ch in clean_chars:
                        tok_end = round(cur_t + step, 3)
                        synth_words.append({"word": ch, "start": round(cur_t, 3), "end": tok_end})
                        cur_t = tok_end

                    word_chunks = split_words_to_safe_chunks(synth_words, min_chunk=min_chunk, max_chars=max_chars, soft_max=soft_max)
                    for c_words in word_chunks:
                        w_text = "".join(x.get("word", "") for x in c_words).strip()
                        if not w_text:
                            continue
                        sub = dict(seg)
                        sub["id"] = f"{seg.get('id', 'seg')}_{len(refined_segments)}"
                        sub["start_time"] = round(float(c_words[0].get("start", cur_clause_start)), 3)
                        sub["end_time"] = round(float(c_words[-1].get("end", clause_end)), 3)
                        sub["raw_text"] = w_text
                        sub["corrected_text"] = w_text
                        sub["words"] = list(c_words)
                        refined_segments.append(sub)

                cur_clause_start = clause_end

        # 拆分后紧接着执行短句碎片平滑合并（保护连续呼吁词如"评论区找我聊一下吧"）
        return self.merge_short_segments(refined_segments, max_chars=max_chars)


    def merge_short_segments(
        self,
        segments: List[Dict[str, Any]],
        min_chars: int = 4,
        min_duration: float = 1.0,
        max_chars: int = 14,
        max_gap: float = 0.55,
        max_duration: float = 3.8
    ) -> List[Dict[str, Any]]:
        """
        短视频口播字幕黄金平滑合并策略（两轮自适应聚合，8~18字弹性）：
        第一轮：优先将相邻的微短词连缀合并（如 "评论区" + "找我" + "聊一下吧" -> "评论区找我聊一下吧"），
        避免前序饱满句子过早将后续呼吁短句拆散；
        第二轮：对于仍然孤立的极小微碎片词（<1.0s 或 <=4字），智能吸附至前后语句中，彻底消除走马灯式的碎词闪烁。
        合并时同步合并 words 列表，完整保留声学物理时间戳。
        """
        import re
        if not segments:
            return []

        def is_short(s):
            dur = s.get("end_time", 0.0) - s.get("start_time", 0.0)
            return len(s.get("raw_text", "").strip()) <= min_chars or dur < min_duration

        def is_retake_guard(text1: str, text2: str) -> bool:
            clean1 = re.sub(r'[^\w\u4e00-\u9fa5]', '', text1)
            clean2 = re.sub(r'[^\w\u4e00-\u9fa5]', '', text2)
            if not clean1 or not clean2:
                return False
            min_l = min(len(clean1), len(clean2))
            if min_l >= 2:
                check_len = min(min_l, 4)
                if clean1[:check_len] == clean2[:check_len]:
                    return True
                if clean2.startswith(clean1) or clean1.startswith(clean2):
                    return True
            return False

        # 第一轮：短片段优先向后连续吸收相邻短片段
        pass1: List[Dict[str, Any]] = []
        i = 0
        while i < len(segments):
            curr = dict(segments[i])
            curr_text = curr.get("raw_text", "").strip()

            while i + 1 < len(segments):
                nxt = segments[i + 1]
                nxt_text = nxt.get("raw_text", "").strip()

                # 重读阻断守卫：前缀重复疑似口误重读时，严禁粘联合并，保持独立切片交由粗剪引擎判断
                if is_retake_guard(curr_text, nxt_text):
                    break

                gap = round(nxt.get("start_time", 0.0) - curr.get("end_time", 0.0), 3)
                prev_ended = bool(re.search(r'[。？！?!]$', curr_text))

                combined_len = len(curr_text) + len(nxt_text)
                combined_dur = round(nxt.get("end_time", 0.0) - curr.get("start_time", 0.0), 3)

                dur_curr = curr.get("end_time", 0.0) - curr.get("start_time", 0.0)
                dur_nxt = nxt.get("end_time", 0.0) - nxt.get("start_time", 0.0)
                is_curr_short = len(curr_text) <= min_chars or dur_curr < min_duration
                is_nxt_short = len(nxt_text) <= min_chars or dur_nxt < min_duration

                is_broken = is_breaking_inseparable_word(curr_text, nxt_text) or is_incomplete_tail(curr_text)
                allowed_len = max_chars + 2 if is_broken else max_chars
                allowed_gap = 1.0 if is_broken else max_gap

                if not prev_ended and 0 <= gap <= allowed_gap and combined_len <= allowed_len and combined_dur <= max_duration:
                    if is_curr_short or is_nxt_short or is_broken:
                        # 如果当前已是字数时长健康的完整句子且后续连续皆为短片段，留给后续短片段自主聚合
                        if not is_broken and not is_curr_short and i + 2 < len(segments) and is_nxt_short and is_short(segments[i + 2]):
                            break

                        curr["end_time"] = nxt.get("end_time", curr["end_time"])
                        curr["raw_text"] = curr_text + nxt_text
                        curr_corr = curr.get("corrected_text", curr_text)
                        nxt_corr = nxt.get("corrected_text", nxt_text)
                        curr["corrected_text"] = curr_corr + nxt_corr
                        if "words" in curr or "words" in nxt:
                            curr["words"] = (curr.get("words") or []) + (nxt.get("words") or [])
                        if "highlight_words" in curr or "highlight_words" in nxt:
                            c_hw = curr.get("highlight_words") or []
                            n_hw = nxt.get("highlight_words") or []
                            seen_words = set()
                            merged_hw = []
                            for w in (c_hw + n_hw):
                                w_val = w.get("word") if isinstance(w, dict) else str(w)
                                if w_val and w_val not in seen_words:
                                    seen_words.add(w_val)
                                    merged_hw.append(w)
                            curr["highlight_words"] = merged_hw
                        curr_text = curr["raw_text"]
                        i += 1
                        continue
                break

            pass1.append(curr)
            i += 1

        # 第二轮：对于仍然孤立的极小微碎片词（<= 4 字或 < 1.0s），向前吸收
        pass2: List[Dict[str, Any]] = []
        for s in pass1:
            if not pass2:
                pass2.append(dict(s))
                continue
            prev = pass2[-1]
            prev_text = prev.get("raw_text", "").strip()
            curr_text = s.get("raw_text", "").strip()

            # 重读阻断守卫：前缀重复时避免被前句逆向吸附
            if is_retake_guard(prev_text, curr_text):
                pass2.append(dict(s))
                continue

            gap = round(s.get("start_time", 0.0) - prev.get("end_time", 0.0), 3)
            prev_ended = bool(re.search(r'[。？！?!]$', prev_text))
            combined_len = len(prev_text) + len(curr_text)
            combined_dur = round(s.get("end_time", 0.0) - prev.get("start_time", 0.0), 3)

            dur = s.get("end_time", 0.0) - s.get("start_time", 0.0)
            is_lone_micro = len(curr_text) <= min_chars or dur < min_duration
            is_broken = is_breaking_inseparable_word(prev_text, curr_text) or is_incomplete_tail(prev_text)

            # 为孤立微碎片词或被切断词设置弹性字数上限与停顿放宽
            micro_limit = max_chars + 2 if (is_lone_micro or is_broken) else max_chars
            allowed_gap = 1.0 if is_broken else max_gap
            if not prev_ended and 0 <= gap <= allowed_gap and combined_len <= micro_limit and combined_dur <= max_duration and (is_lone_micro or is_broken):
                prev["end_time"] = s.get("end_time", prev["end_time"])
                prev["raw_text"] = prev_text + curr_text
                prev["corrected_text"] = prev.get("corrected_text", prev_text) + s.get("corrected_text", curr_text)
                if "words" in prev or "words" in s:
                    prev["words"] = (prev.get("words") or []) + (s.get("words") or [])
                if "highlight_words" in prev or "highlight_words" in s:
                    p_hw = prev.get("highlight_words") or []
                    s_hw = s.get("highlight_words") or []
                    seen_words = set()
                    merged_hw = []
                    for w in (p_hw + s_hw):
                        w_val = w.get("word") if isinstance(w, dict) else str(w)
                        if w_val and w_val not in seen_words:
                            seen_words.add(w_val)
                            merged_hw.append(w)
                    prev["highlight_words"] = merged_hw
            else:
                pass2.append(dict(s))

        return pass2

    def smooth_subtitle_timings(
        self,
        segments: List[Dict[str, Any]],
        lead_in: float = 0.07,
        max_fill_gap: float = 0.60,
        trailing_hold: float = 0.25,
        final_hold: float = 0.30
    ) -> List[Dict[str, Any]]:
        """
        短视频口播字幕时序平滑与无缝接力策略（彻底消除走马灯黑屏闪烁与滞后感）：
        1. 听觉前置量 (70ms)：提前 70ms 呈现字幕，与人眼识别与声学起始冲激对齐；
        2. 微停顿自然接力 (gap <= 0.6s)：在常规呼吸或自然意群停顿间隙，当前字幕平滑延留至下一句开始，无缝接力切换；
        3. 长停顿自然阅读延留 (gap > 0.6s)：延留 250ms 供阅读，然后自然清屏，进入真正停顿/转场；
        4. 尾句保护：末句延留 300ms，避免语音刚落字幕瞬间熄灭。
        """
        if not segments:
            return []

        smoothed = []
        for i, s in enumerate(segments):
            item = dict(s)
            curr_start = float(item.get("start_time", 0.0))
            curr_end = float(item.get("end_time", 0.0))

            if i > 0:
                prev_end = float(smoothed[i - 1].get("end_time", 0.0))
                eff_start = max(prev_end, round(curr_start - lead_in, 3))
            else:
                eff_start = max(0.0, round(curr_start - lead_in, 3))

            if i + 1 < len(segments):
                next_start = float(segments[i + 1].get("start_time", 0.0))
                gap = round(next_start - curr_end, 3)
                if 0 < gap <= max_fill_gap:
                    next_eff_start = max(curr_end, round(next_start - lead_in, 3))
                    eff_end = next_eff_start
                else:
                    eff_end = min(next_start, round(curr_end + trailing_hold, 3))
            else:
                eff_end = round(curr_end + final_hold, 3)

            if eff_end <= eff_start:
                eff_end = max(eff_start + 0.3, curr_end)

            item["start_time"] = eff_start
            item["end_time"] = eff_end
            smoothed.append(item)

        return smoothed

    def parse_minimax_response(self, resp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将 MiniMax asr-1.0 接口 verbose_json 返回的逐字 segments 映射为系统标准的 words 与句子分段：
        1. 遍历字级 segments，提取字符、起止时间戳；
        2. 基于标点、声学静音间隙（gap >= 0.28s）、自然语气词与字数健康度划分自然句；
        3. 每句包含 words: List[{word, start, end}]，保留完整的声学物理时间戳供后续高亮与黄金切分使用。
        """
        import re
        raw_segments = []
        minimax_segments = resp_data.get("segments") or []
        if not minimax_segments:
            text = resp_data.get("text", "").strip()
            if text:
                return [{
                    "start_time": 0.0,
                    "end_time": float(resp_data.get("duration", 0.0)),
                    "raw_text": text,
                    "corrected_text": text,
                    "words": []
                }]
            return []

        # 规范化：若 segment 包含内嵌标点或复合短语，拆分为原子单元并按字长线性插值时间戳
        flat_segments = []
        for item in minimax_segments:
            text = item.get("text", "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            tokens = [t for t in re.split(r'([,，;；!！?？。、\s]+)', text) if t]
            if len(tokens) <= 1:
                flat_segments.append({"start": start, "end": end, "text": text})
                continue

            non_punct_len = sum(len(re.sub(r'[,，;；!！?？。、\s]', '', t)) for t in tokens)
            dur = max(0.0, end - start)
            cur_t = start
            for tok in tokens:
                if re.match(r'^[,，;；!！?？。、\s]+$', tok):
                    flat_segments.append({"start": cur_t, "end": cur_t, "text": tok})
                else:
                    clean_len = len(re.sub(r'[,，;；!！?？。、\s]', '', tok))
                    tok_dur = (clean_len / non_punct_len * dur) if non_punct_len > 0 else 0.0
                    tok_end = round(cur_t + tok_dur, 3)
                    flat_segments.append({"start": cur_t, "end": tok_end, "text": tok})
                    cur_t = tok_end

        current_words = []
        for idx, item in enumerate(flat_segments):
            text = item.get("text", "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start))
            is_pure_punct = bool(re.search(r'^[,，;；!！?？。、\s]+$', text))
            has_trailing_punct = bool(re.search(r'[,，;；!！?？。、\s]+$', text))
            clean_word = re.sub(r'[,，;；!！?？。、\s]', '', text)

            if clean_word:
                current_words.append({"word": clean_word, "start": round(start, 3), "end": round(end, 3)})

            next_start = float(flat_segments[idx + 1].get("start", end)) if idx + 1 < len(flat_segments) else end
            gap = max(0.0, next_start - end)
            curr_len = sum(len(x["word"]) for x in current_words)

            # 语义断句：优先基于标点（纯标点或词尾附带标点）、明显声学停顿（>=0.40s 且 >=8字）、语气词停顿
            # 彻底废除 curr_len >= 14 的机械硬切，超长句交由 split_into_readable_segments 按语法意群切分
            should_break = (
                is_pure_punct or
                has_trailing_punct or
                (gap >= 0.40 and curr_len >= 8) or
                (curr_len >= 6 and gap >= 0.20 and (text[-1:] in "呢吧啊吗呀啦哒哦哈" or (clean_word and clean_word[-1:] in "呢吧啊吗呀啦哒哦哈")))
            )

            # 语义完整性守卫：严禁在不可分词中间就地断开（如"想要了/解"），避免碎片化
            if should_break and idx + 1 < len(flat_segments):
                next_tok = flat_segments[idx + 1].get("text", "")
                next_clean = re.sub(r'[,，;；!！?？。、\s]', '', next_tok)
                curr_tail = "".join(x["word"] for x in current_words)
                if is_breaking_inseparable_word(curr_tail, next_clean):
                    should_break = False
            if should_break and current_words:
                clause_text = "".join(x["word"] for x in current_words).strip()
                clause_text = re.sub(r'[,，;；!！?？。、\s]+$', '', clause_text).strip()
                if clause_text:
                    raw_segments.append({
                        "id": f"s_{len(raw_segments) + 1}",
                        "start_time": current_words[0]["start"],
                        "end_time": current_words[-1]["end"],
                        "raw_text": clause_text,
                        "corrected_text": clause_text,
                        "words": list(current_words)
                    })
                current_words = []

        if current_words:
            clause_text = "".join(x["word"] for x in current_words).strip()
            clause_text = re.sub(r'[,，;；!！?？。、\s]+$', '', clause_text).strip()
            if clause_text:
                raw_segments.append({
                    "id": f"s_{len(raw_segments) + 1}",
                    "start_time": current_words[0]["start"],
                    "end_time": current_words[-1]["end"],
                    "raw_text": clause_text,
                    "corrected_text": clause_text,
                    "words": list(current_words)
                })

        return self.filter_filler_segments(raw_segments)

    def transcribe_minimax(
        self,
        audio_path: Path,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0
    ) -> List[Dict[str, Any]]:
        """
        通过 MiniMax 云端 asr-1.0 接口极速识别语音，获取字级时间戳。
        """
        from app.core import config
        key = (api_key or config.get_minimax_api_key() or "").strip()
        if not key:
            raise ValueError("未配置 MiniMax API Key，无法使用 MiniMax 云端语音识别")

        url = (base_url or config.get_minimax_base_url() or "https://api.minimaxi.com/v1").rstrip("/")
        if not url.endswith("/speech_to_text"):
            stt_endpoint = f"{url}/speech_to_text"
        else:
            stt_endpoint = url

        headers = {
            "Authorization": f"Bearer {key}"
        }
        data = {
            "model": "asr-1.0",
            "response_format": "verbose_json",
            "timestamp_level": "word",
            "stream": "false"
        }

        import time
        max_retries = 3
        backoffs = [1.0, 2.5, 5.0]
        resp_json = None
        last_exc = None

        with _asr_concurrency_lock:
            for attempt in range(max_retries):
                try:
                    with open(audio_path, "rb") as f:
                        files = {
                            "file": (audio_path.name, f, "audio/wav")
                        }
                        res = httpx.post(stt_endpoint, headers=headers, data=data, files=files, timeout=timeout)
                        try:
                            res.raise_for_status()
                        except httpx.HTTPStatusError as e:
                            # 尝试解析 MiniMax 返回的详细 JSON 报错信息并增强异常提示
                            try:
                                err_data = res.json()
                                msg = None
                                if isinstance(err_data, dict):
                                    if "error" in err_data:
                                        err_info = err_data["error"]
                                        if isinstance(err_info, dict) and "message" in err_info:
                                            msg = err_info["message"]
                                        elif isinstance(err_info, str):
                                            msg = err_info
                                    elif "base_resp" in err_data:
                                        msg = err_data["base_resp"].get("status_msg")
                                if msg:
                                    e.args = (f"{e.args[0]} - {msg}",)
                            except Exception:
                                pass
                            raise
                        resp_json = res.json()
                        break
                except (httpx.HTTPError, OSError, ValueError, Exception) as e:
                    last_exc = e
                    # 4xx 客户端错误中除 429 外直接抛出，不进行无意义重试
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                        raise
                    if attempt < max_retries - 1:
                        sleep_sec = backoffs[attempt] + random.uniform(0.05, 0.25)
                        print(f"[ASRRunner] MiniMax ASR 请求瞬时网络或解析异常 ({type(e).__name__}: {e})，将在 {sleep_sec:.2f}s 后进行第 {attempt + 2}/{max_retries} 次重试...")
                        time.sleep(sleep_sec)
                    else:
                        print(f"[ASRRunner] MiniMax ASR 请求已达最大重试次数 ({max_retries} 次)，最终失败: {e}")
                        raise

        if resp_json is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("MiniMax ASR 重试耗尽未获取有效响应")

        base_resp = resp_json.get("base_resp")
        if base_resp and base_resp.get("status_code", 0) != 0:
            msg = base_resp.get("status_msg", "MiniMax STT 识别接口返回错误")
            raise RuntimeError(f"MiniMax ASR 接口错误: {msg} (code: {base_resp.get('status_code')})")

        return self.parse_minimax_response(resp_json)

    def _transcribe_local(self, video_path: Path, audio_tmp: Path, extracted: bool) -> List[Dict[str, Any]]:
        """本地 Faster-Whisper ASR 已全面停用，统一使用 MiniMax 云端极速识别"""
        raise NotImplementedError("本地 ASR 已停用，系统统一接入 MiniMax 云端极速语音识别。")

    def transcribe(self, video_path: Path) -> List[Dict[str, Any]]:
        """
        对口播视频进行语音识别，返回【自然句层】的原始字幕（不切割）。
        统一调用 MiniMax 云端极速 ASR (asr-1.0)，获取毫秒级字时间戳。已彻底停用本地 Faster-Whisper。
        """
        from app.core import config
        minimax_key = config.get_minimax_api_key()
        if not minimax_key:
            raise RuntimeError("未配置 MiniMax API Key，本地 ASR 已停用，请在系统设置中配置 MiniMax API Key")

        audio_tmp = video_path.parent / f"{video_path.stem}_audio_{int(time.time()*1000)}.wav"
        try:
            extracted = self.extract_audio(video_path, audio_tmp)
            if not extracted:
                raise RuntimeError(
                    f"从口播视频 ({video_path.name}) 中提取纯音频流失败，无法提交 MiniMax ASR 转写。"
                    f"请确认运行环境中包含有效的 FFmpeg 可执行组件。"
                )
            target_audio = audio_tmp if audio_tmp.exists() else video_path

            print(f"[ASRRunner] 使用 MiniMax 云端极速 ASR 转写音频: {target_audio.name} (来源: {video_path.name})")
            segments = self.transcribe_minimax(
                target_audio,
                api_key=minimax_key,
                base_url=config.get_minimax_base_url()
            )
            if not segments:
                raise RuntimeError(f"MiniMax 云端 ASR 语音识别返回空结果: {video_path.name}")
            for idx, s in enumerate(segments):
                if not s.get("id"):
                    s["id"] = f"s_{idx + 1}"
            return segments
        finally:
            if audio_tmp.exists():
                try:
                    audio_tmp.unlink()
                except Exception:
                    pass

asr_runner = ASRRunner()
