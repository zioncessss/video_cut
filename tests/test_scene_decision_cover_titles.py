"""012-US2: AI 伴随式封面文案与地域词提取单测（全部离线，严禁真实联网调用）。"""
import pytest

from app.native_engine.scene_decision import parse_cue_sheet, generate_fallback_cover_titles
from app.harness_bridge.prompting import build_scene_decision_prompt
from app.models.entities import SuggestedCoverTitle


def _subs():
    return [
        {"id": "0", "start_time": 0.0, "end_time": 3.0, "corrected_text": "杭州学车一定要注意这个避坑指南"},
        {"id": "1", "start_time": 3.0, "end_time": 6.0, "corrected_text": "教练手把手教学一口价全包"},
    ]


def test_prompt_includes_cover_title_instructions_with_location_tag():
    prompt = build_scene_decision_prompt(_subs())
    assert "suggested_cover_titles" in prompt
    assert "爆款封面标题组" in prompt
    assert "location_tag" in prompt, "提示词必须指令提取同城地域地名锚点"
    for template_id in (
        "sticker_double_stroke", "split_contrast_bar", "rainbow_arc_header",
        "bottom_fog_vignette", "angled_impact_stamp", "clean_editorial",
    ):
        assert template_id in prompt, f"提示词 style_hint 枚举缺少 {template_id}"


def test_parse_cue_sheet_with_location_tag_and_rationale():
    raw_response = """
    {
      "video_title": "杭州学车大改革：一口价全包手把手教",
      "suggested_cover_titles": [
        {"location_tag": "武义学车", "main_title": "学车避坑指南", "sub_title": "一口价全包",
         "rationale": "直击价格痛点并锚定同城流量", "style_hint": "sticker_double_stroke"},
        {"location_tag": "金东学车", "main_title": "3个技巧一把过", "sub_title": "新手必看",
         "style_hint": "rainbow_arc_header"}
      ],
      "broll_cues": [
        {"start_time": 3.0, "end_time": 6.0, "category": "lesson", "visual_intent": "教练带教示范"}
      ],
      "highlights": {
        "0": [{"word": "杭州", "category": "location"}],
        "1": [{"word": "一口价", "category": "price"}]
      }
    }
    """
    cuelist = parse_cue_sheet(raw_response)
    assert cuelist.video_title == "杭州学车大改革：一口价全包手把手教"
    assert len(cuelist.suggested_cover_titles) == 2
    first = cuelist.suggested_cover_titles[0]
    assert first["location_tag"] == "武义学车"
    assert first["main_title"] == "学车避坑指南"
    assert first["rationale"] == "直击价格痛点并锚定同城流量"
    assert first["style_hint"] == "sticker_double_stroke"
    assert cuelist.suggested_cover_titles[1]["location_tag"] == "金东学车"
    # 不影响既有 highlights 解析
    assert cuelist.highlights["1"][0]["word"] == "一口价"


def test_parse_cue_sheet_legacy_response_compat():
    """旧版大模型响应无 location_tag/rationale 字段时兼容为空串，不得抛错"""
    raw_response = """
    {
      "video_title": "杭州学车大改革",
      "suggested_cover_titles": [
        {"main_title": "学车避坑指南", "sub_title": "一口价全包", "style_hint": "gold_bold"}
      ],
      "broll_cues": [],
      "highlights": {}
    }
    """
    cuelist = parse_cue_sheet(raw_response)
    assert len(cuelist.suggested_cover_titles) == 1
    item = cuelist.suggested_cover_titles[0]
    assert item["location_tag"] == ""
    assert item["rationale"] == ""
    assert item["style_hint"] == "gold_bold"


def test_prompt_injects_cover_hooks_library_and_few_shot_examples():
    """内置提示词必须注入词库 cover_hooks 学车特点库与真实爆款风格实例"""
    prompt = build_scene_decision_prompt(_subs())
    assert "学车特点库" in prompt, "提示词必须注入学车特点库"
    assert "费用全透明" in prompt, "特点库词条应来自 glossary.json cover_hooks"
    assert "2980明码标价" in prompt, "必须包含真实爆款双标题风格实例"
    assert "严禁编造" in prompt, "必须约束口播中不存在的数字不得编造"


def test_fallback_cover_titles_extract_location_from_glossary_engine():
    subs = [
        {"id": "0", "start_time": 0.0, "end_time": 3.0, "corrected_text": "在杭州学车的朋友注意了"},
        {"id": "1", "start_time": 3.0, "end_time": 6.0, "corrected_text": "报名前一定要看清收费明细"},
    ]
    titles = generate_fallback_cover_titles(subs, video_title="杭州驾校一口价改革")
    assert titles, "离线兜底必须产出候选，不允许空列表"
    assert titles[0]["location_tag"] == "杭州学车"
    assert all(t["rationale"].startswith("离线规则兜底") for t in titles), "兜底候选必须如实标注规则来源"
    assert all(t["main_title"] for t in titles)

    # 特点库可用时，库选用条目（非视频标题派生条目）的 main_title 必须来自库中
    from app.native_engine.scene_decision import _load_cover_hooks
    hooks = _load_cover_hooks()
    if hooks:
        assert titles[1]["main_title"] in hooks, "特点库可用时兜底主标题必须从库中选用"


def test_fallback_cover_titles_filter_venue_facility_words():
    """训练场/考场等场地设施词不得充当封面地域锚点"""
    subs = [{"id": "0", "start_time": 0.0, "end_time": 3.0, "corrected_text": "我们训练场五万平"}]
    titles = generate_fallback_cover_titles(subs)
    assert all(t["location_tag"] == "" for t in titles)
    # 词库可用时主标题来自特点库；词库缺失时回退规格预设话术，两者均合法
    from app.native_engine.scene_decision import _load_cover_hooks
    hooks = _load_cover_hooks()
    legal_mains = set(hooks[:2]) | {"驾校学车避坑指南", "3个技巧快速拿证"}
    for t in titles:
        assert t["main_title"] in legal_mains


def test_suggested_cover_title_model_fields():
    item = SuggestedCoverTitle(location_tag="婺城学车", main_title="场地全包一口价", rationale="同城锚点")
    assert item.style_hint == "sticker_double_stroke"
    assert item.sub_title == ""
    dumped = item.model_dump()
    assert set(dumped.keys()) == {"location_tag", "main_title", "sub_title", "rationale", "style_hint"}
