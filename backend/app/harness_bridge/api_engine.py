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

        # 上下文纪律：仅角色+词库背景+精简 {id, text}，不携带工程状态/素材库/历史
        clean_input = [
            {"id": s.get("id"), "text": s.get("raw_text") or s.get("corrected_text", "")}
            for s in request.raw_subtitles
        ]
        prompt = build_correction_prompt(clean_input)

        success, output_str, latency_ms = await llm_client.chat_completion(prompt, timeout=45.0)
        if success:
            data = llm_client.extract_json(output_str)
            if isinstance(data, dict) and isinstance(data.get("subtitles"), list):
                return self._assemble_response(request, data, latency_ms)

        # 解析失败/网络失败：降级词库确定性纠偏，引擎标识如实标注降级链
        fallback_res = await self._fallback.correct_subtitles(request)
        fallback_res.harness_engine_used = f"api (fallback embedded: {('解析失败' if success else output_str[:80])})"
        fallback_res.latency_ms = round(latency_ms, 1)
        return fallback_res

    def _assemble_response(
        self,
        request: HarnessCorrectionRequest,
        data: Dict[str, Any],
        latency_ms: float,
    ) -> HarnessCorrectionResponse:
        corr_text_map = {
            str(item.get("id")): item.get("corrected_text")
            for item in data.get("subtitles", [])
            if isinstance(item, dict) and item.get("id")
        }
        hl_map = {
            str(item.get("id")): item.get("highlight_keywords", [])
            for item in data.get("subtitles", [])
            if isinstance(item, dict) and item.get("id")
        }
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
        for orig in request.raw_subtitles:
            seg = dict(orig)
            sid = str(seg.get("id"))
            if sid in corr_text_map and corr_text_map[sid]:
                seg["corrected_text"] = corr_text_map[sid]
            else:
                seg["corrected_text"] = seg.get("corrected_text") or seg.get("raw_text", "")
            seg["corrected_text"], _ = apply_glossary_corrections(str(seg["corrected_text"]))
            ai_words = hl_map.get(sid) if isinstance(hl_map.get(sid), list) else []
            if sid in hl_map and isinstance(hl_map[sid], list):
                existing_kw = seg.get("matched_keywords", []) or []
                seg["matched_keywords"] = list(dict.fromkeys(existing_kw + hl_map[sid]))
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
        """AI 分镜决策通道：150s 超时（实测 91~127s），失败/解析失败如实返回 ok=False 由调用方降级"""
        from app.native_engine.scene_decision import parse_decisions

        if not await self.is_available():
            return [], "api (unavailable)", 0.0, False
        from app.harness_bridge.prompting import build_scene_decision_prompt
        prompt = build_scene_decision_prompt(subtitles)
        success, output_str, latency_ms = await llm_client.chat_completion(prompt, timeout=150.0)
        if success:
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
