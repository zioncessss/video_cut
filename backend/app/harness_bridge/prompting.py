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
        f"3. 【严禁修改讲者真实原话】：文字上讲者本人口播说的真实词汇绝对不要去修改或同义润色！受保护词（绝对禁止改写）：{protected_hint}。保持讲者真实口语用词，非 ASR 错字一律保留原文。\n"
        "4. 【地名绝对保护红线】：仅纠偏口音导致的明显错字（如'福州'纠正为'湖州'）；若讲者口播明确提及的是其他真实城市（如'杭州'、'萧山'、'宁波'、'绍兴'等），绝对严禁篡改为词库默认城市！地名篡改属于严重违规事故！\n\n"
        "【任务二：短视频核心重点词提取与色彩视觉感知】：\n"
        "短视频字幕必须抓住完播率与信任感。请为每句提取 1~2 个最关键的高价值锚点词（highlight_words），宁缺毋滥（单句无核心重点则返回空列表 []，严禁全句大面积高亮）！根据语义类型给出专属高亮颜色（十六进制代码）：\n"
        "1. 地名/区域/校区（category: 'location'，首选亮青蓝 '#38BDF8'）：城市名（如杭州、湖州等）、区域/商圈（如余杭、萧山、临平、西湖等）、校区/训练场/考场。地名是同城推流第一信任抓手，凡涉及地名一律提取高亮！\n"
        "2. 费用/收费/价格/保障（category: 'price'，首选鲜亮红 '#EF4444' 或醒目黄 '#FACC15'）：具体金额数字（如 2980、两千八、300块）、收费项目（如练车费、补训费、燃油费、模拟费、报名费、学费、补考费、体检费等各类费用词）、收费保障与痛点（一口价、全包、无隐形消费、透明收费、避坑、吃拿卡要、乱收费）。【排比句高度对称纪律】：当口播连续多句提及并列费用（如连续说'不收练车费'、'不收补训费'、'不收燃油费'、'不收模拟费'）时，必须保持高度对称性，同类费用词必须全部提取高亮，严禁前后随机遗漏！\n"
        "3. 考点/技能动作/承诺（category: 'exam'，首选亮黄 '#FACC15'）：科目二、科目三、倒库、侧方停车、一把过、免排队、手把手教学、极速拿证。\n"
        "4. 纯白大字视觉强调（category: 'white'，纯白 '#FFFFFF'）：短视频纯白加粗大字在无色差干扰下极具杂志高级感。仅用于核心观点或业务痛点词（如'避坑'、'全包'、'踩坑'）！\n"
        "5. 【严禁高亮无意义虚词】：情态助词/副词（如'一定要'、'可能'、'其实'、'应该'、'非常'、'特别'、'很多'、'千万'）、代词（如'我们'、'大家'、'这个'、'那个'、'这些'）、连词/助词（如'如果'、'但是'、'或者是'、'的话'）绝对禁止打高亮标签！\n"
        "6. 【关于 corrections 纠错明细的纪律】：仅在真正修改了同音错别字时才记录到 corrections 数组中（必须 original_text != corrected_text）；若全句无错字，corrections 必须返回空列表 []，严禁输出原词等于纠正词的无意义自嗨项！\n\n"
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
            "id": str(s.get("id") if s.get("id") is not None else idx),
            "start": round(float(s.get("start_time", 0.0)), 2),
            "end": round(float(s.get("end_time", 0.0)), 2),
            "text": str(s.get("corrected_text") or s.get("raw_text") or "")
        }
        for idx, s in enumerate(subtitles)
    ]

    return (
        "你是驾校口播短视频的智能剪辑导演。口播视频原声与字幕全程保留，你的任务有三个：\n"
        "1. 【提炼爆款短视频标题 (video_title)】：通读全篇口播与地域重点，提炼一个 10~18 字以内直击学员痛点/焦点的短视频爆款标题（如'杭州驾校迎来大改革！学车一口价全包手把手教学'，通俗吸睛、杜绝虚假）；\n"
        "2. 【智能空镜切入指示 (broll_cues)】：识别与以下三类场景【强相关】的语段，并输出建议切入空镜的区间清单；\n"
        "3. 【大模型自主语义高光词提取 (highlights)】：请充分发挥大模型的地理常识与商业语义理解能力，为每句自主提取 1~2 个最关键的高价值词（宁缺毋滥，无重点句子对应空数组 []）：\n"
        "   - 【地名/区域/校区 (category: 'location')】：充分发挥你的中国地理知识库，自主识别任何省/市/区/县/街道/地标（如'安吉'、'富阳'、'诸暨'、'义乌'、'桐庐'、'德清'、'余杭'、'西湖'等任意区县名，依靠地理常识自主提取，切勿局限于少数大城市！）；\n"
        "   - 【费用/保障/痛点 (category: 'price')】：具体金额、各类费用项（补训费、燃油费、模拟费、学费等）、收费承诺（一口价、全包、透明收费、无隐形消费等）。【排比句高度对称】：连续提及费用时同类项必须全部高亮，严禁前后遗漏！\n"
        "   - 【考点/技能/承诺 (category: 'exam')】：科目二、倒库、一把过、手把手教学等。\n\n"
        "【空镜大类与匹配优先级】：\n"
        "1. lesson: 教学练车空镜（优先强匹配！提到练车细节、教练带教、科目二/三、打方向、倒库、半坡、起步等动作）\n"
        "2. venue: 场地空镜（提到训练场、考场、校区、门店、五万平、周边实景环境等）\n"
        "3. experience: 体验空镜（提到报名咨询、体检、拍照、拿证等学员流程）\n\n"
        f"【地域背景】：{background_hint}\n\n"
        "【三大严禁切镜红线（绝对禁止输出切镜区间）】：\n"
        "1. 开场前 1.8 秒口播真人亮相（主播出镜建立信任），前 1.8 秒内绝对不要切镜；\n"
        "2. 价格手势句：比划报价话术（如「这个数」「这个价」「这么多」）绝不切镜，手势本身是内容；\n"
        "3. 结尾行动召唤句（如「评论区找我聊」「点红心」「私信我」等 CTA）绝不切镜。\n\n"
        "【导演原则与输出规范】：\n"
        "- 仅输出强相关的空镜区间！无需逐句打标，不要输出不切空镜的段落（普通段落由系统编排层自适应随机铺底）；\n"
        "- 单处空镜建议区间为 3~5 秒（start_time 与 end_time 必须严格对齐字幕的发音起止时间）；\n"
        "- 严格只返回纯 JSON，没有任何 Markdown 标记或额外解释，格式如下：\n"
        "{\n"
        '  "video_title": "杭州驾校迎来大改革：学车一口价全包手把手教学",\n'
        '  "broll_cues": [\n'
        '    {"start_time": 18.5, "end_time": 23.2, "category": "venue", "visual_intent": "低价套路引出驾校实景门面"}\n'
        '  ],\n'
        '  "highlights": {\n'
        '    "0": [{"word": "湖州", "category": "location"}],\n'
        '    "1": [{"word": "安吉", "category": "location"}]\n'
        '  }\n'
        "}\n\n"
        f"【待决策口播字幕时间轴】：\n{json.dumps(clean_subs, ensure_ascii=False)}"
    )
