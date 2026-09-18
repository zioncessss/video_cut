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
        "你是一个专业的驾校短视频口播字幕语义纠偏与视觉重点导演助手。\n"
        "【核心背景与地域信息】（来自本地词库 glossary.json）：\n"
        f"- {background_hint}\n\n"
        "【任务一：同音错字智能纠偏准则】：\n"
        f"1. 仅纠正 ASR 听写产生的同音错别字，词库既定纠偏映射（长词优先，务必遵守）：{correction_examples}。未列出的同音错字按语境纠正。\n"
        "2. 【逐句严格对应】：输入几句就必须输出几句，每句的 id 原样保留、一一对应；严禁合并句子、拆分句子、调整顺序、增删句子。\n"
        f"3. 【严禁修改讲者真实原话】：文字上讲者本人口播说的真实词汇绝对不要去修改或同义润色！受保护词（绝对禁止改写）：{protected_hint}。保持讲者真实口语用词，非 ASR 错字一律保留原文。\n\n"
        "【任务二：短视频核心重点词提取与色彩视觉感知】：\n"
        "短视频字幕必须抓住完播率与信任感。请为每句提取 1~3 个最关键的高亮词（highlight_words），并根据语义类型给出专属高亮颜色（十六进制代码）：\n"
        "1. 地名/区域/校区（category: 'location'，首选亮青蓝 '#38BDF8' 或纯白 '#FFFFFF'）：城市名（如杭州、湖州等）、区域/商圈（如余杭、萧山、临平、西湖等）、校区/训练场/考场。地名是同城推流第一信任抓手，凡涉及地名一律提取高亮！\n"
        "2. 费用/收费/价格/保障（category: 'price'，首选鲜亮红 '#EF4444' 或醒目黄 '#FACC15'）：具体金额数字（如 2980、两千八、300块）、收费项目（报名费、学费、补考费、模拟费、体检费）、收费保障与痛点（一口价、全包、无隐形消费、透明收费、避坑、吃拿卡要、乱收费）。费用是学员最核心关切，凡涉及收费/费用一律提取高亮！\n"
        "3. 考点/技能动作/承诺（category: 'exam'，首选亮黄 '#FACC15' 或纯白 '#FFFFFF'）：科目二、科目三、倒库、侧方停车、一把过、免排队、手把手教学、极速拿证。\n"
        "4. 白色高亮视觉选择（category: 'white'，纯白 '#FFFFFF'）：短视频中纯白加粗文字配合发光放大，极具专业度与冲击力！当遇到强语气词、转折词（如'千万不要'、'一定要'、'全包'、'真的'、'必须'、'避坑'）或核心卖点时，可智能返回纯白 '#FFFFFF'。\n\n"
        f"待纠错口播文本列表（已精简）：\n{json.dumps(clean_input, ensure_ascii=False)}\n\n"
        "请严格返回如下结构的纯 JSON，不要包含任何额外说明或 Markdown 标签：\n"
        "{\n"
        '  "subtitles": [\n'
        '    {\n'
        '      "id": "...",\n'
        '      "corrected_text": "纠正后的文本",\n'
        '      "highlight_words": [\n'
        '        {"word": "杭州", "color": "#38BDF8", "category": "location"},\n'
        '        {"word": "2980", "color": "#EF4444", "category": "price"}\n'
        '      ]\n'
        '    }\n'
        '  ],\n'
        '  "corrections": [\n'
        '    {"subtitle_id": "...", "original_text": "原词", "corrected_text": "纠正词", "reason": "修改原因"}\n'
        '  ]\n'
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
        "【空镜大类与匹配优先级】：\n"
        "1. lesson: 教学练车空镜（优先强匹配！提到练车细节、教练带教、科目二/三、打方向、倒库、半坡、起步等动作）\n"
        "2. venue: 场地空镜（提到训练场、考场、校区、门店、五万平、周边实景环境等）\n"
        "3. experience: 体验空镜（提到报名咨询、体检、拍照、拿证等学员流程）\n\n"
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
