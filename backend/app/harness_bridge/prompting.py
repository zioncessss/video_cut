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
        "2. 【逐句严格对应】：输入几句就必须输出几句，每句的 id 原样保留、一一对应；严禁合并句子、拆分句子、调整顺序、增删句子。很多输入句是长句的截断片段（如'…迎来大改革我'与'们现学车…'），错别字只需在各自句内修正，绝不要跨越句边界改写。\n"
        f"3. 【严禁修改讲者真实原话】：文字上讲者本人口播说的真实词汇绝对不要去修改或同义润色！受保护词（绝对禁止改写）：{protected_hint}。例如讲者说的是'老师'，严禁修改为'教练'！保持讲者真实口语用词，非 ASR 错字一律保留原文。\n"
        "4. 提取每句中最核心的 1~2 个高亮重点词。\n\n"
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
    分镜决策提示词：采纳稀疏剪辑指示清单（Editorial Cue Sheet）模式。
    仅识别强相关语义区间（场地实景 venue、教练带教 lesson、学员流程 experience），
    不输出不切的段落，彻底消除 Token 膨胀截断；普通正文区间由本地编排层自适应随机铺底以达成 60%~70% 覆盖率。
    """
    glossary = load_glossary()
    loc = glossary.get("location") or {}
    background_hint = str(loc.get("prompt_hint", "")).strip() or "（词库未配置背景信息）"

    # 精简输入字幕字段，极速传输
    clean_subs = [
        {
            "start": round(float(s.get("start_time", 0.0)), 2),
            "end": round(float(s.get("end_time", 0.0)), 2),
            "text": str(s.get("corrected_text") or s.get("raw_text") or "")
        }
        for s in subtitles
    ]

    return (
        "你是驾校口播短视频的智能剪辑导演。口播视频原声与字幕全程保留，"
        "你的唯一任务是：通读全篇口播与时间戳，敏锐识别其中与以下三类场景【强相关】的语段，并输出建议切入空镜的区间清单（broll_cues）。\n\n"
        "【空镜大类】：\n"
        "- venue: 场地空镜（提到训练场/考场/校区/门店/周边实景）\n"
        "- lesson: 教学练车空镜（提到教练带教/打方向/倒库侧方/练车画面）\n"
        "- experience: 体验空镜（提到报名咨询/体检/拿证/上车体验等学员流程）\n\n"
        f"【地域背景】：{background_hint}\n\n"
        "【三大严禁切镜红线（绝对禁止输出切镜区间）】：\n"
        "1. 开场前 1.8 秒口播真人亮相（主播出镜建立信任），前 1.8 秒内绝对不要切镜；\n"
        "2. 价格手势句：比划报价话术（如「这个数」「这个价」「这么多」）绝不切镜，手势本身是核心内容；\n"
        "3. 结尾行动召唤句（如「评论区找我聊」「点红心」「私信我」等 CTA）绝不切镜。\n\n"
        "【导演原则与输出规范】：\n"
        "- 仅输出强相关的空镜区间！无需逐句打标，不要输出不切空镜的段落（普通段落由系统编排层自适应随机铺底）；\n"
        "- 单处空镜建议区间为 3~5 秒（start_time 与 end_time 必须严格对齐字幕的发音起止时间）；\n"
        "- 严格只返回纯 JSON，没有任何 Markdown 标记或额外解释，格式如下：\n"
        "{\n"
        '  "broll_cues": [\n'
        '    {"start_time": 18.5, "end_time": 23.2, "category": "venue", "visual_intent": "低价套路引出驾校实景门面"}\n'
        "  ]\n"
        "}\n\n"
        f"【待决策口播字幕时间轴】：\n{json.dumps(clean_subs, ensure_ascii=False)}"
    )
