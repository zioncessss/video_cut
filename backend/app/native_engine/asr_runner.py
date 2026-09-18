import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
import re

class ASRRunner:
    def __init__(self):
        self._model = None

    def extract_audio(self, video_path: Path, output_audio_path: Path) -> bool:
        """从视频中抽取 16kHz 单声道 wav 音频以供 ASR 识别"""
        try:
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(output_audio_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            return res.returncode == 0
        except Exception as e:
            print(f"Audio extraction error: {e}")
            return False

    FILLER_PATTERN = re.compile(r'^[呃额嗯唔啊诶哎呀喔噢]+[，。？！…\s]*$|^[eE][hH]|[uU][mM]|[aA][hH]$')

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

    def split_into_readable_segments(
        self,
        segments: List[Dict[str, Any]],
        max_chars: int = 18,
        soft_max: Optional[int] = None,
        min_chunk: int = 5
    ) -> List[Dict[str, Any]]:
        """
        针对口播短视频进行 8~18 字自然意群与视读切分（带防孤字、防碎尾与弹性意群保护）：
        1. 针对健康单行（<= soft_max，默认 20~22 字），不盲目硬拆，完整保留自然意群（如“还有一个就是大家通常不知道的就是模拟费”19字完整保留）；
        2. 若长句必须切分，执行严格的防孤字保护：严禁剩余字数 < min_chunk (5字)，彻底根除诸如“模拟 / 费”、“要多 / 少钱”等荒谬单字碎尾；
        3. 优先在自然标点、语气助词、语法连词或声学停顿处切分；
        4. 切分后自动执行局部微短碎片吸附。
        """
        refined_segments = []
        import re

        if soft_max is None:
            soft_max = max(max_chars + 2, 22) if max_chars >= 16 else max_chars

        CONJ_PATTERN = re.compile(r'^(在|从|到|让|如果|但是|然后|因为|所以|比如|还有|而且|可以说是|特别是|也就是|大家)')
        # 中文自然意群切分正则：在语气词后、或在自然引词/连词前断句（防御性负向前瞻避免拆开"像我们在"等）
        split_pattern = re.compile(
            r'(?<=[呢吧啊吗呀啦哒哦哈])|'
            r'(?<!像)(?=(?:我们在|像我们在|像我们|我们|你们|他们|真的没有|真的|其实|大家|如果|但是|而且|然后|只要|不要|因为|所以|比如|另外|可以说是|特别))'
        )

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
                curr_words = []
                clause_chunks = []
                for idx_w, w in enumerate(words):
                    curr_words.append(w)
                    curr_len = sum(len(x.get("word", "")) for x in curr_words)
                    rem_words = words[idx_w + 1:]
                    rem_len = sum(len(x.get("word", "")) for x in rem_words)

                    if not rem_words:
                        break

                    next_w = rem_words[0]
                    gap = round(next_w.get("start", 0.0) - w.get("end", 0.0), 3)

                    # 若当前字数加上剩余字数已在 soft_max 范围内，不再强行切断，直接留给整句
                    if curr_len + rem_len <= soft_max:
                        continue

                    # 防孤字保护准则：剩余字数必须 >= min_chunk (5字)，严防 1~4 字单字/孤儿碎尾
                    has_safe_tail = (rem_len >= min_chunk)
                    should_split_here = has_safe_tail and (
                        (curr_len >= max_chars) or
                        (curr_len >= 8 and gap >= 0.22) or
                        (curr_len >= 6 and gap >= 0.40) or
                        (curr_len >= 8 and bool(CONJ_PATTERN.match("".join(x.get("word", "") for x in rem_words[:2]))))
                    )

                    if should_split_here:
                        w_text = "".join(x.get("word", "") for x in curr_words).strip()
                        if w_text:
                            sub = dict(seg)
                            sub["id"] = f"{seg.get('id', 'seg')}_{len(refined_segments) + len(clause_chunks)}"
                            sub["start_time"] = round(curr_words[0].get("start", start), 3)
                            sub["end_time"] = round(curr_words[-1].get("end", end), 3)
                            sub["raw_text"] = w_text
                            sub["corrected_text"] = w_text
                            sub["words"] = list(curr_words)
                            clause_chunks.append(sub)
                        curr_words = []

                if curr_words:
                    w_text = "".join(x.get("word", "") for x in curr_words).strip()
                    if clause_chunks and len(w_text) < min_chunk:
                        # 孤儿碎尾安全吸附进前一段
                        clause_chunks[-1]["end_time"] = round(curr_words[-1].get("end", end), 3)
                        clause_chunks[-1]["raw_text"] += w_text
                        clause_chunks[-1]["corrected_text"] += w_text
                        clause_chunks[-1]["words"] = (clause_chunks[-1].get("words") or []) + list(curr_words)
                    elif w_text:
                        sub = dict(seg)
                        sub["id"] = f"{seg.get('id', 'seg')}_{len(refined_segments) + len(clause_chunks)}"
                        sub["start_time"] = round(curr_words[0].get("start", start), 3)
                        sub["end_time"] = round(curr_words[-1].get("end", end), 3)
                        sub["raw_text"] = w_text
                        sub["corrected_text"] = w_text
                        sub["words"] = list(curr_words)
                        clause_chunks.append(sub)

                refined_segments.extend(clause_chunks)
                continue

            # 方案 B：无词级时间戳，采用自然语法意群与标点智能切分（彻底废除 chunk_len=10 机械截断）
            raw_clauses = [c.strip() for c in re.split(r'[,，;；!！?？。、\s]+', text) if c.strip()]
            final_sub_chunks = []
            for clause in raw_clauses:
                if len(clause) <= soft_max:
                    final_sub_chunks.append(clause)
                else:
                    parts = [p.strip() for p in split_pattern.split(clause) if p and p.strip()]
                    expanded_parts = []
                    for p in parts:
                        if len(p) <= soft_max:
                            expanded_parts.append(p)
                        else:
                            # 尝试按常见助词/介词切分
                            sub_pieces = [sp for sp in re.split(r'(?<=[的了在和与到去及以从向])', p) if sp]
                            temp = ""
                            for sp in sub_pieces:
                                if not temp:
                                    temp = sp
                                elif len(temp) + len(sp) <= max_chars:
                                    temp += sp
                                else:
                                    expanded_parts.append(temp)
                                    temp = sp
                            if temp:
                                expanded_parts.append(temp)
                    final_parts = []
                    for ep in expanded_parts:
                        while len(ep) > max_chars + 2:
                            split_idx = max_chars
                            final_parts.append(ep[:split_idx])
                            ep = ep[split_idx:]
                        if ep:
                            final_parts.append(ep)

                    curr = ""
                    for p in final_parts:
                        if not curr:
                            curr = p
                        elif len(curr) + len(p) <= max_chars:
                            curr += p
                        else:
                            final_sub_chunks.append(curr)
                            curr = p
                    if curr:
                        final_sub_chunks.append(curr)

            if not final_sub_chunks:
                refined_segments.append(seg)
                continue

            total_chars = sum(len(c) for c in final_sub_chunks)
            curr_time = start
            for i, chunk in enumerate(final_sub_chunks):
                chunk_dur = duration * (len(chunk) / max(1, total_chars))
                chunk_end = end if i == len(final_sub_chunks) - 1 else curr_time + chunk_dur

                sub_seg = dict(seg)
                sub_seg["id"] = f"{seg.get('id', 'seg')}_{i}"
                sub_seg["start_time"] = round(curr_time, 3)
                sub_seg["end_time"] = round(chunk_end, 3)
                sub_seg["raw_text"] = chunk
                sub_seg["corrected_text"] = chunk
                refined_segments.append(sub_seg)
                curr_time = chunk_end

        # 拆分后紧接着执行短句碎片平滑合并（保护连续呼吁词如"评论区找我聊一下吧"）
        return self.merge_short_segments(refined_segments, max_chars=max_chars)


    def merge_short_segments(
        self,
        segments: List[Dict[str, Any]],
        min_chars: int = 4,
        min_duration: float = 1.0,
        max_chars: int = 18,
        max_gap: float = 0.55,
        max_duration: float = 4.2
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

        # 第一轮：短片段优先向后连续吸收相邻短片段
        pass1: List[Dict[str, Any]] = []
        i = 0
        while i < len(segments):
            curr = dict(segments[i])
            curr_text = curr.get("raw_text", "").strip()

            while i + 1 < len(segments):
                nxt = segments[i + 1]
                nxt_text = nxt.get("raw_text", "").strip()
                gap = round(nxt.get("start_time", 0.0) - curr.get("end_time", 0.0), 3)
                prev_ended = bool(re.search(r'[。？！?!]$', curr_text))

                combined_len = len(curr_text) + len(nxt_text)
                combined_dur = round(nxt.get("end_time", 0.0) - curr.get("start_time", 0.0), 3)

                dur_curr = curr.get("end_time", 0.0) - curr.get("start_time", 0.0)
                dur_nxt = nxt.get("end_time", 0.0) - nxt.get("start_time", 0.0)
                is_curr_short = len(curr_text) <= min_chars or dur_curr < min_duration
                is_nxt_short = len(nxt_text) <= min_chars or dur_nxt < min_duration

                if not prev_ended and 0 <= gap <= max_gap and combined_len <= max_chars and combined_dur <= max_duration:
                    if is_curr_short or is_nxt_short:
                        # 如果当前已是字数时长健康的完整句子(>=8字且>=1.5s)，且后续连续皆为短片段，留给后续短片段自主聚合
                        if not is_curr_short and i + 2 < len(segments) and is_nxt_short and is_short(segments[i + 2]):
                            break

                        curr["end_time"] = nxt.get("end_time", curr["end_time"])
                        curr["raw_text"] = curr_text + nxt_text
                        curr_corr = curr.get("corrected_text", curr_text)
                        nxt_corr = nxt.get("corrected_text", nxt_text)
                        curr["corrected_text"] = curr_corr + nxt_corr
                        if "words" in curr or "words" in nxt:
                            curr["words"] = (curr.get("words") or []) + (nxt.get("words") or [])
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
            gap = round(s.get("start_time", 0.0) - prev.get("end_time", 0.0), 3)
            prev_ended = bool(re.search(r'[。？！?!]$', prev_text))
            combined_len = len(prev_text) + len(curr_text)
            combined_dur = round(s.get("end_time", 0.0) - prev.get("start_time", 0.0), 3)

            dur = s.get("end_time", 0.0) - s.get("start_time", 0.0)
            is_lone_micro = len(curr_text) <= min_chars or dur < min_duration

            # 为孤立微碎片词设置微弹性字数上限 (max_chars + 2，如 20 字)，确保诸如 18 + 1 的孤儿能被强力吸附
            micro_limit = max_chars + 2 if is_lone_micro else max_chars
            if not prev_ended and 0 <= gap <= max_gap and combined_len <= micro_limit and combined_dur <= max_duration and is_lone_micro:
                prev["end_time"] = s.get("end_time", prev["end_time"])
                prev["raw_text"] = prev_text + curr_text
                prev["corrected_text"] = prev.get("corrected_text", prev_text) + s.get("corrected_text", curr_text)
                if "words" in prev or "words" in s:
                    prev["words"] = (prev.get("words") or []) + (s.get("words") or [])
            else:
                pass2.append(dict(s))

        return pass2

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

            # 语义断句：优先基于标点（纯标点或词尾附带标点）、明显声学停顿（>=0.28s）、语气词停顿
            # 彻底废除 curr_len >= 14 的机械硬切，超长句交由 split_into_readable_segments 按语法意群切分
            should_break = (
                is_pure_punct or
                has_trailing_punct or
                (gap >= 0.28 and curr_len >= 5) or
                (curr_len >= 6 and ((gap >= 0.15 and text[-1:] in "呢吧啊吗呀啦哒哦哈") or (clean_word and clean_word[-1:] in "呢吧啊吗呀啦哒哦哈" and gap >= 0.12)))
            )
            if should_break and current_words:
                clause_text = "".join(x["word"] for x in current_words).strip()
                clause_text = re.sub(r'[,，;；!！?？。、\s]+$', '', clause_text).strip()
                if clause_text:
                    raw_segments.append({
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

        with open(audio_path, "rb") as f:
            files = {
                "file": (audio_path.name, f, "audio/wav")
            }
            res = httpx.post(stt_endpoint, headers=headers, data=data, files=files, timeout=timeout)
            res.raise_for_status()
            resp_json = res.json()

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
        audio_tmp = video_path.parent / f"{video_path.stem}_audio.wav"
        try:
            extracted = self.extract_audio(video_path, audio_tmp)
            target_audio = audio_tmp if extracted and audio_tmp.exists() else video_path

            minimax_key = config.get_minimax_api_key()
            if not minimax_key:
                raise RuntimeError("未配置 MiniMax API Key，本地 ASR 已停用，请在系统设置中配置 MiniMax API Key")

            print(f"[ASRRunner] 使用 MiniMax 云端极速 ASR 转写: {video_path.name}")
            segments = self.transcribe_minimax(
                target_audio,
                api_key=minimax_key,
                base_url=config.get_minimax_base_url()
            )
            if not segments:
                raise RuntimeError(f"MiniMax 云端 ASR 语音识别返回空结果: {video_path.name}")
            return segments
        finally:
            if audio_tmp.exists():
                try:
                    audio_tmp.unlink()
                except Exception:
                    pass

asr_runner = ASRRunner()
