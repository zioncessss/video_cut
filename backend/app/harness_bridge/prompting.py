"""Harness 纠错提示词工厂：全链路唯一由 storage/glossary.json 驱动的提示词构造器。

codex / zcode 等 LLM 型桥接器共用，杜绝各自硬编码纠偏知识。
"""
import json
from typing import List, Dict, Any

from app.core.config import load_glossary


def build_correction_prompt(clean_input: List[Dict[str, Any]]) -> str:
    """由词库生成字幕语义纠偏提示词：背景知识、纠偏映射示例、受保护词全部来自 glossary.json"""
    glossary = load_glossary()
    loc = glossary.get("location") or {}
    corrections = glossary.get("common_corrections") or {}
    protected_words = [str(w) for w in (glossary.get("protected_words") or [])]

    background_hint = str(loc.get("prompt_hint", "")).strip() or "（词库未配置背景信息）"
    correction_examples = "、".join(
        f"'{k}'->'{v}'"
        for k, v in sorted(corrections.items(), key=lambda kv: len(str(kv[0])), reverse=True)[:10]
    ) or "（词库未配置纠偏映射）"
    protected_hint = "、".join(protected_words) if protected_words else "（暂无）"

    return (
        "你是一个专业的驾校短视频口播字幕语义纠偏助手。\n"
        "【核心背景与地域信息】（来自本地词库 glossary.json）：\n"
        f"- {background_hint}\n\n"
        "【纠偏核心准则】：\n"
        f"1. 仅纠正 ASR 听写产生的同音错别字，词库既定纠偏映射（长词优先，务必遵守）：{correction_examples}。未列出的同音错字按语境纠正。\n"
        f"2. 【严禁修改讲者真实原话】：文字上讲者本人口播说的真实词汇绝对不要去修改或同义润色！受保护词（绝对禁止改写）：{protected_hint}。例如讲者说的是'老师'，严禁修改为'教练'！保持讲者真实口语用词，非 ASR 错字一律保留原文。\n"
        "3. 提取每句中最核心的 1~2 个高亮重点词。\n\n"
        f"待纠错口播文本列表（已精简）：\n{json.dumps(clean_input, ensure_ascii=False)}\n\n"
        "请严格返回如下结构的纯 JSON，不要包含任何额外说明或 Markdown 标签：\n"
        "{\n"
        '  "subtitles": [\n'
        '    {"id": "...", "corrected_text": "纠正后的文本", "highlight_keywords": ["重点词"]}\n'
        "  ],\n"
        '  "corrections": [\n'
        '    {"subtitle_id": "...", "original_text": "原词", "corrected_text": "纠正词", "reason": "修改原因"}\n'
        "  ]\n"
        "}"
    )


def build_scene_decision_prompt(subtitles: List[Dict[str, Any]]) -> str:
    """
    分镜决策提示词（词库驱动 + 真实口播风格规则，详见 specs/005 research.md R8）：
    AI 只负责「切哪类/切多久/转场多久」的画面决策，高亮词职责归纠偏调用。
    输出严格 JSON，后端还会过确定性校验（双保险），此处规则与后端校验保持一致。
    """
    glossary = load_glossary()
    loc = glossary.get("location") or {}
    background_hint = str(loc.get("prompt_hint", "")).strip() or "（词库未配置背景信息）"

    return (
        "你是驾校口播短视频的智能剪辑师。口播视频的音轨与字幕全程保留自原口播，"
        "你的唯一任务是：为每一句字幕决策【是否切空镜画面】。空镜分类：\n"
        "- venue：场地空镜（训练场/考场/校区/门店/周边道路实景）\n"
        "- experience：体验空镜（报名咨询/体检/试学体验/拿证/上车体验等学员流程画面）\n"
        "- lesson：教学空镜（教练带教/打方向/倒库侧方练车画面）\n\n"
        f"【地域背景】{background_hint}\n\n"
        "【硬性不切规则——命中必须返回 null】：\n"
        "1. 开场钩子（前几句建立真人信任的悬念/地域提问）不切；\n"
        "2. 价格手势句：出现「这个数」「这个价」「这么多」等比划报价话术时绝对不切，画面手势本身就是内容；\n"
        "3. 结尾行动召唤（滴滴我/找我聊/点红心/觉得怎么样/报名都没有关系）不切；\n"
        "4. 情绪叙事与讲故事段落（痛点共鸣/学员故事/内心承诺）尽量不切，保留真人表情感染力。\n\n"
        "【节奏约束】：\n"
        "- 不允许相邻两句连续切空镜（至少间隔一句口播）；\n"
        "- 全片空镜总时长占比不超过 40%；\n"
        "- 单处空镜时长取该句时长的 60%~100%；转场时长 0.3~0.5 秒。\n\n"
        "【字幕列表】（字段：id / text 文本 / start_time 开始秒 / end_time 结束秒）：\n"
        + json.dumps(subtitles, ensure_ascii=False)
        + "\n\n严格只返回纯 JSON，无任何 markdown 与解释：\n"
        "{\n"
        '  "decisions": [\n'
        '    {"id": "...", "part": "hook|body|cta", "broll": "venue|experience|lesson|null", '
        '"broll_duration": 2.0, "transition": 0.4, "reason": "一句话理由"}\n'
        "  ]\n"
        "}"
    )
