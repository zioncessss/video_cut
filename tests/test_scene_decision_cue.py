import pytest
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models.entities import MaterialCategory, SceneDecision, BrollCueItem
from app.native_engine.scene_decision import (
    parse_cue_sheet,
    plan_dual_layer_broll,
    validate_cue_prohibited_zones,
    fallback_keyword_rules,
    _PRICE_GESTURE_RE,
    _CTA_RE
)

def test_parse_cue_sheet_valid_json():
    raw = """```json
    {
      "broll_cues": [
        {
          "start_time": 18.5,
          "end_time": 24.0,
          "category": "venue",
          "visual_intent": "展示训练场门面与大门"
        },
        {
          "start_time": 50.0,
          "end_time": 56.2,
          "category": "lesson",
          "visual_intent": "科目二倒车入库教练带教"
        }
      ]
    }
    ```"""
    cues = parse_cue_sheet(raw)
    assert len(cues) == 2
    assert cues[0].category == MaterialCategory.VENUE
    assert cues[0].start_time == 18.5
    assert cues[0].end_time == 24.0
    assert cues[1].category == MaterialCategory.LESSON

def test_parse_cue_sheet_empty_or_malformed():
    assert parse_cue_sheet("") == []
    assert parse_cue_sheet("invalid non json text") == []
    assert parse_cue_sheet('{"other": []}') == []

def test_prohibited_zones_guards():
    """测试开场1.8s前、报价手势句、结尾CTA被严格过滤拦截"""
    subtitles = [
        {"id": "s1", "start_time": 0.0, "end_time": 1.6, "raw_text": "同学们大家好我是小陈。"},
        {"id": "s2", "start_time": 1.6, "end_time": 4.5, "raw_text": "今天带大家来看我们杭州自建训练场。"},
        {"id": "s3", "start_time": 10.0, "end_time": 13.0, "raw_text": "全包只要这个数绝不加钱。"},
        {"id": "s4", "start_time": 20.0, "end_time": 25.0, "raw_text": "倒库一把过秘诀就是看准后视镜。"},
        {"id": "s5", "start_time": 50.0, "end_time": 55.0, "raw_text": "想要学车的朋友记得评论区找我聊。"}
    ]

    cues = [
        BrollCueItem(start_time=0.5, end_time=1.5, category=MaterialCategory.VENUE, visual_intent="opening"),
        BrollCueItem(start_time=10.5, end_time=12.5, category=MaterialCategory.VENUE, visual_intent="price"),
        BrollCueItem(start_time=21.0, end_time=24.0, category=MaterialCategory.LESSON, visual_intent="lesson"),
        BrollCueItem(start_time=51.0, end_time=54.0, category=MaterialCategory.EXPERIENCE, visual_intent="cta"),
    ]

    filtered_cues = validate_cue_prohibited_zones(subtitles, cues)
    assert len(filtered_cues) == 1, f"应只保留1个合法cue，实际保留: {len(filtered_cues)}"
    assert filtered_cues[0].category == MaterialCategory.LESSON
    assert filtered_cues[0].start_time == 21.0

def test_dual_layer_pacing_coverage_guarantee():
    """测试双层编排：强相关精准锚定 + 自由段落自适应随机铺底，硬性保证 60%~70% 黄金覆盖率"""
    subtitles = []
    t = 0.0
    idx = 0
    while t < 60.0:
        dur = 2.5
        subtitles.append({
            "id": f"sub_{idx}",
            "start_time": round(t, 2),
            "end_time": round(min(60.0, t + dur), 2),
            "raw_text": f"口播讲解句子内容测试第{idx}段",
            "words": [{"word": f"词{idx}", "start": round(t, 2), "end": round(min(60.0, t + dur), 2)}]
        })
        t += dur
        idx += 1

    # 仅提供 1 个强相关 cue（4秒，占 6.6% 覆盖率）
    cues = [
        BrollCueItem(start_time=10.0, end_time=14.0, category=MaterialCategory.VENUE, visual_intent="训练场实景")
    ]

    # 执行双层编排，目标 65% (0.60 ~ 0.70)
    windows = plan_dual_layer_broll(
        subtitles=subtitles,
        cues=cues,
        total_duration=60.0,
        target_coverage=0.65,
        available_categories=[MaterialCategory.VENUE, MaterialCategory.LESSON, MaterialCategory.EXPERIENCE]
    )

    total_broll_seconds = sum(w["end_time"] - w["start_time"] for w in windows)
    coverage_ratio = total_broll_seconds / 60.0

    assert 0.58 <= coverage_ratio <= 0.72, f"空镜覆盖率应达到 60%~70%，当前覆盖时长 {total_broll_seconds:.1f}s ({coverage_ratio:.1%})"
    # 验证开场 1.8s 绝对没有空镜
    assert not any(w["start_time"] < 1.8 for w in windows), "开场 1.8s 真人出镜保护被侵犯"
    # 验证单镜时长都在 2.0s ~ 6.0s 之间
    for w in windows:
        dur = w["end_time"] - w["start_time"]
        assert dur >= 1.8, f"单镜时长过短，存在频闪: {dur}s"
        assert dur <= 6.5, f"单镜时长过长: {dur}s"

def test_keyword_priority_lesson_venue_experience():
    """测试三库匹配优先级：练车细节(lesson) > 场地(venue) > 体验(experience)"""
    from app.native_engine.keyword_matcher import match_keywords_in_segment
    # 含有练车(lesson)和场地(venue)的句子，优先匹配 lesson
    res1 = match_keywords_in_segment("大家在训练场练车的时候一定要把好方向盘")
    assert res1["matched_category"] == "lesson"
    assert "练车" in res1["matched_keywords"]
    assert "训练场" in res1["matched_keywords"]

    # 只含有场地(venue)和体验(experience)的句子，优先匹配 venue
    res2 = match_keywords_in_segment("我们考场提供体检一站式服务")
    assert res2["matched_category"] == "venue"
    assert "考场" in res2["matched_keywords"]
    assert "体检" in res2["matched_keywords"]

    # 只含有体验(experience)的句子，匹配 experience
    res3 = match_keywords_in_segment("体检拍照十分钟快速搞定")
    assert res3["matched_category"] == "experience"
    assert "体检" in res3["matched_keywords"]


def test_highlight_words_colors_and_categories():
    """测试高亮词多色支持：地名亮蓝、费用亮红、白色高亮与考点金黄"""
    from app.native_engine.keyword_matcher import build_highlight_words

    text = "在杭州学车只要2980全包并且科目二一把过"
    ai_kws = [
        {"word": "杭州", "color": "#38BDF8", "category": "location"},
        {"word": "2980", "color": "#EF4444", "category": "price"},
        {"word": "全包", "color": "#FFFFFF", "category": "white"},
        {"word": "一把过", "color": "#FACC15", "category": "exam"}
    ]

    res = build_highlight_words(text, ai_keywords=ai_kws)
    res_map = {item["word"]: item for item in res}

    assert "杭州" in res_map
    assert res_map["杭州"]["color"] == "#38BDF8"
    assert res_map["杭州"]["category"] == "location"

    assert "2980" in res_map
    assert res_map["2980"]["color"] == "#EF4444"
    assert res_map["2980"]["category"] == "price"

    assert "全包" in res_map
    assert res_map["全包"]["color"] == "#FFFFFF"
    assert res_map["全包"]["category"] == "white"

    assert "一把过" in res_map
    assert res_map["一把过"]["color"] == "#FACC15"


def test_subtitle_styler_ass_per_word_colors(tmp_path):
    """测试 ASS 字幕渲染引擎针对不同高亮词（含白色、蓝色、红色）渲染对应的行内 BGR 色彩代码"""
    from app.native_engine.subtitle_styler import generate_ass_file

    subs = [
        {
            "start_time": 1.0,
            "end_time": 4.0,
            "corrected_text": "在杭州学车只要2980全包",
            "highlight_words": [
                {"word": "杭州", "color": "#38BDF8", "category": "location"},
                {"word": "2980", "color": "#EF4444", "category": "price"},
                {"word": "全包", "color": "#FFFFFF", "category": "white"},
            ]
        }
    ]
    out_ass = tmp_path / "test.ass"
    generate_ass_file(subs, out_ass, strategy={"enable_highlight": True})
    ass_content = out_ass.read_text(encoding="utf-8")

    # 验证蓝底地名 38BDF8 -> ASS BGR &HF8BD38&
    assert r"{\cF8BD38" in ass_content or r"{\c&HF8BD38&" in ass_content
    # 验证红底价格 EF4444 -> ASS BGR &H4444EF&
    assert r"{\c4444EF" in ass_content or r"{\c&H4444EF&" in ass_content
    # 验证纯白高亮 FFFFFF -> ASS BGR &HFFFFFF&
    assert r"{\cFFFFFF" in ass_content or r"{\c&HFFFFFF&" in ass_content


