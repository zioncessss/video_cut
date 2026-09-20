"""直连大模型 API 桥接器（Tier A：固定格式任务专用引擎）。

字幕纠偏等格式固定的调用走 OpenAI 兼容 /chat/completions 直连：
提示词由词库工厂生成（上下文只含角色+词库背景+精简字幕列表），
返回结果过词库确定性兜底。开放式任务（自由指令/聊天）不在本引擎职责内，
自动路由至 Tier B（codex/zcode CLI 代理）。
"""
from typing import List, Dict, Any

from app.harness_bridge.base import (
    BaseHarnessBridge,
    HarnessCorrectionRequest,
    HarnessCorrectionResponse,
    SubtitleCorrectionItem,
    HarnessInstructionRequest,
    HarnessPlanResponse,
)
from app.harness_bridge.embedded import EmbeddedHarnessBridge
from app.harness_bridge.prompting import build_correction_prompt
from app.harness_bridge import llm_client
from app.core.config import apply_glossary_corrections

# 纠偏分块：按 ≤12 句一块请求控制爆炸半径；流式收集完整回复（推理模型思考链长，
# 非流式 45s 必超时——实测 11 句需 82s），流式下超时只约束 token 间空闲，生成本身不限时
CORRECTION_CHUNK_SIZE = 12
CORRECTION_STREAM_IDLE_TIMEOUT = 120.0


class ApiHarnessBridge(BaseHarnessBridge):
    """OpenAI 兼容直连引擎：无需 node/codex 本地依赖，打包产物开箱可用。"""

    def __init__(self):
        self._fallback = EmbeddedHarnessBridge()
        self._tier_b = None  # 延迟解析，避免工厂循环依赖

    async def is_available(self) -> bool:
        return llm_client.resolve_api_provider() is not None

    def _get_tier_b(self) -> BaseHarnessBridge:
        if self._tier_b is None:
            from app.harness_bridge.factory import get_tier_b_harness
            self._tier_b = get_tier_b_harness()
        return self._tier_b

    async def correct_subtitles(self, request: HarnessCorrectionRequest) -> HarnessCorrectionResponse:
        if not await self.is_available():
            fallback_res = await self._fallback.correct_subtitles(request)
            fallback_res.harness_engine_used = "api (fallback embedded: provider not configured)"
            return fallback_res

        # 确保每个字幕都有唯一 ID，并且构建 clean_input
        for i, s in enumerate(request.raw_subtitles):
            if not s.get("id"):
                s["id"] = f"s_{i + 1}"

        # 上下文纪律：仅角色+词库背景+精简 {id, text}，不携带工程状态/素材库/历史
        clean_input = [
            {"id": s.get("id"), "text": s.get("raw_text") or s.get("corrected_text", "")}
            for s in request.raw_subtitles
        ]
        chunks = [
            clean_input[i:i + CORRECTION_CHUNK_SIZE]
            for i in range(0, len(clean_input), CORRECTION_CHUNK_SIZE)
        ] or [clean_input]

        def _norm_id(val):
            return str(val).strip().lower().replace("s_", "").replace("seg_", "").replace("s", "")

        merged_subtitles: List[Dict[str, Any]] = []
        merged_corrections: List[Dict[str, Any]] = []
        failures: List[str] = []
        latency_ms = 0.0
        for idx, chunk in enumerate(chunks):
            prompt = build_correction_prompt(chunk)
            success, output_str, latency_ms = await llm_client.chat_completion_stream_full(
                prompt, timeout=CORRECTION_STREAM_IDLE_TIMEOUT
            )
            data = llm_client.extract_json(output_str) if success else None
            if success and isinstance(data, dict) and isinstance(data.get("subtitles"), list):
                # 句集一致性校验：模型返回的 id 集合必须与输入完全一致，
                # 防止模型自行合并/拆分/调序导致纠偏文本错位到别的句子上
                sent_ids = {_norm_id(s.get("id")) for s in chunk if s.get("id") is not None}
                returned_ids = {_norm_id(it.get("id")) for it in data["subtitles"] if isinstance(it, dict) and it.get("id") is not None}
                if (sent_ids and returned_ids == sent_ids) or (len(chunk) == len(data["subtitles"]) and all(isinstance(it, dict) and it.get("corrected_text") for it in data["subtitles"])):
                    # 补齐/对其原始 ID，确保与 request.raw_subtitles 严格对齐
                    for i_sub, it in enumerate(data["subtitles"]):
                        if i_sub < len(chunk):
                            orig_id = chunk[i_sub].get("id")
                            if orig_id:
                                it["id"] = orig_id
                    merged_subtitles.extend(data.get("subtitles") or [])
                    raw_corrs = data.get("corrections") or []
                    actual_corrs = [
                        c for c in raw_corrs
                        if isinstance(c, dict)
                        and str(c.get("original_text", "")).strip() != str(c.get("corrected_text", "")).strip()
                        and str(c.get("original_text", "")).strip() != ""
                    ]
                    merged_corrections.extend(actual_corrs)
                    continue
                # 模型重新断句（输入为长句/碎片时常见）：模型的重断句恰恰更符合语言习惯——
                # 取其纠偏全文作为整块内容，按比例重新映射回该块时间线（黄金切割本就是比例插值）
                full_text = "".join(
                    str(it.get("corrected_text") or "")
                    for it in data["subtitles"]
                    if isinstance(it, dict)
                )
                full_text, glossary_changes = apply_glossary_corrections(full_text)
                if glossary_changes:
                    merged_corrections.append({
                        "subtitle_id": next(iter(sent_ids), ""),
                        "original_text": "、".join(ch["from"] for ch in glossary_changes),
                        "corrected_text": "、".join(ch["to"] for ch in glossary_changes),
                        "changes": glossary_changes,
                    })
                if full_text.strip():
                    try:
                        from app.native_engine.asr_runner import asr_runner
                        chunk_start = min(float(s.get("start_time", 0) or 0) for s in chunk)
                        chunk_end = max(float(s.get("end_time", 0) or 0) for s in chunk)
                        pieces = asr_runner.split_into_readable_segments([{
                            "id": f"{next(iter(sent_ids), 'chunk')}-rs",
                            "start_time": chunk_start,
                            "end_time": chunk_end,
                            "corrected_text": full_text,
                        }])
                        if pieces:
                            merged_subtitles.extend(pieces)
                            continue
                    except Exception as split_err:
                        print(f"[ApiEngine] 重断句重映射失败，回退词库: {split_err}")
                reason = "模型返回句集与输入不一致，已回退词库纠偏"
            else:
                reason = output_str[:80] if not success else "解析失败"
            # 该块失败：词库确定性兜底，句子绝不丢失；原因如实记录
            failures.append(f"块{idx + 1}/{len(chunks)}: {reason}")
            for s in chunk:
                text, _ = apply_glossary_corrections(str(s.get("text", "")))
                merged_subtitles.append({"id": s.get("id"), "corrected_text": text})

        if len(failures) == len(chunks):
            # 全部块失败：整体降级 embedded，引擎标识如实标注降级链
            fallback_res = await self._fallback.correct_subtitles(request)
            fallback_res.harness_engine_used = f"api (fallback embedded: {failures[0]})"
            fallback_res.latency_ms = round(latency_ms, 1)
            return fallback_res

        res = self._assemble_response(
            request, {"subtitles": merged_subtitles, "corrections": merged_corrections}, latency_ms
        )
        if failures:
            res.harness_engine_used = f"api (partial fallback embedded: {'; '.join(failures)})"
        return res

    def _assemble_response(
        self,
        request: HarnessCorrectionRequest,
        data: Dict[str, Any],
        latency_ms: float,
    ) -> HarnessCorrectionResponse:
        def _norm_id(val):
            return str(val).strip().lower().replace("s_", "").replace("seg_", "").replace("s", "")

        corr_text_map: Dict[str, Any] = {}
        hl_map: Dict[str, Any] = {}
        for idx_it, item in enumerate(data.get("subtitles", [])):
            if isinstance(item, dict):
                iid = item.get("id")
                raw_hl = item.get("highlight_words") or item.get("highlight_keywords") or []
                c_txt = item.get("corrected_text")
                if iid is not None:
                    corr_text_map[str(iid)] = c_txt
                    corr_text_map[_norm_id(iid)] = c_txt
                    hl_map[str(iid)] = raw_hl
                    hl_map[_norm_id(iid)] = raw_hl
                # 保留下标备用
                corr_text_map[f"idx_{idx_it}"] = c_txt
                hl_map[f"idx_{idx_it}"] = raw_hl

        corrections_summary = [
            SubtitleCorrectionItem(
                subtitle_id=str(c.get("subtitle_id", "")),
                original_text=str(c.get("original_text", "")),
                corrected_text=str(c.get("corrected_text", "")),
                changes=[{"from": str(c.get("original_text", "")), "to": str(c.get("corrected_text", "")), "reason": str(c.get("reason", "智能语义纠错"))}]
            )
            for c in (data.get("corrections") or []) if isinstance(c, dict)
        ]

        # 回填原始时间戳；词库确定性兜底（幂等），防模型漏纠
        from app.core.config import apply_glossary_corrections
        from app.native_engine.keyword_matcher import build_highlight_words
        final_subtitles = []
        for idx_orig, orig in enumerate(request.raw_subtitles):
            seg = dict(orig)
            sid = str(seg.get("id"))
            nid = _norm_id(sid)
            matched_corr = corr_text_map.get(sid) or corr_text_map.get(nid) or corr_text_map.get(f"idx_{idx_orig}")
            if matched_corr:
                seg["corrected_text"] = matched_corr
            else:
                seg["corrected_text"] = seg.get("corrected_text") or seg.get("raw_text", "")
            seg["corrected_text"], _ = apply_glossary_corrections(str(seg["corrected_text"]))

            raw_ai = hl_map.get(sid) or hl_map.get(nid) or hl_map.get(f"idx_{idx_orig}") or []
            ai_words = raw_ai if isinstance(raw_ai, list) else []
            if ai_words:
                existing_kw = seg.get("matched_keywords", []) or []
                clean_kws = [
                    (w.get("word") if isinstance(w, dict) else str(w))
                    for w in ai_words
                    if (isinstance(w, dict) and w.get("word")) or (isinstance(w, str) and w)
                ]
                seg["matched_keywords"] = list(dict.fromkeys(existing_kw + clean_kws))
            # 三源高亮：词库命中（glossary 优先）∪ AI 判定（ai），幂等去重
            seg["highlight_words"] = build_highlight_words(str(seg["corrected_text"]), ai_words)
            final_subtitles.append(seg)

        return HarnessCorrectionResponse(
            updated_subtitles=final_subtitles,
            corrections_summary=corrections_summary,
            harness_engine_used="api",
            latency_ms=round(latency_ms, 1)
        )

    async def decide_scenes(self, subtitles: List[Dict[str, Any]]):
        """AI 分镜决策通道：流式收集完整回复，解析稀疏指示清单 (broll_cues)，
        失败/解析失败如实返回 ok=False 由调用方降级关键词规则"""
        from app.native_engine.scene_decision import parse_cue_sheet, parse_decisions

        if not await self.is_available():
            return [], "api (unavailable)", 0.0, False
        from app.harness_bridge.prompting import build_scene_decision_prompt
        prompt = build_scene_decision_prompt(subtitles)
        success, output_str, latency_ms = await llm_client.chat_completion_stream_full(prompt, timeout=60.0)
        if success:
            cues = parse_cue_sheet(output_str)
            if cues:
                return cues, "api", latency_ms, True
            # 兼容旧格式 decisions
            decisions = parse_decisions(output_str)
            if decisions:
                return decisions, "api", latency_ms, True
            return [], "api (解析失败)", latency_ms, False
        return [], f"api ({output_str[:80]})", latency_ms, False

    async def apply_natural_instruction(self, request: HarnessInstructionRequest) -> HarnessPlanResponse:
        """开放式指令不在直连引擎职责内，路由 Tier B（codex/zcode → embedded 链）"""
        return await self._get_tier_b().apply_natural_instruction(request)

    # generate_batch_variations 已删除：全项目无消费方，继承 base 默认显式报错

    async def stream_chat(self, prompt: str, model_override: str = None):
        async for chunk in self._get_tier_b().stream_chat(prompt, model_override=model_override):
            yield chunk

    async def ping(self, model_override: str = None) -> Any:
        """连通性探针：流式请求测量首 Token 延迟（TTFT），只含网络与提示词处理，不含完整生成"""
        provider = llm_client.resolve_api_provider() or {}
        if not provider:
            return False, "", 0.0, "未配置直连提供方：请在设置页填写 base_url 与 api_key，或确保 ~/.codex/config.toml 存在"
        active_model = (model_override or provider.get("model") or "").strip()
        success, ttft_ms, detail = await llm_client.chat_completion_ttft(
            'Output only a single valid JSON object: {"status": "ok"}. No other text or markdown.',
            timeout=20.0,
            model_override=model_override
        )
        if success:
            return True, active_model, ttft_ms, f"直连连通正常，首 Token {ttft_ms:.0f} ms（来源：{provider.get('source')}）"
        return False, active_model, ttft_ms, f"直连调用失败: {detail}"
