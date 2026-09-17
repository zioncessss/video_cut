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
