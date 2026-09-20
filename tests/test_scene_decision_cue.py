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
    generate_fallback_video_title,
    _PRICE_GESTURE_RE,
    _CTA_RE
)

def test_parse_cue_sheet_valid_json():
    raw = """```json
    {
      "video_title": "杭州驾校迎来大改革：学车一口价全包手把手教学",
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
    assert getattr(cues, "video_title", None) == "杭州驾校迎来大改革：学车一口价全包手把手教学"

def test_parse_cue_sheet_with_highlights():
    raw = """```json
    {
      "video_title": "安吉学车新政策",
      "broll_cues": [
        {
          "start_time": 5.0,
          "end_time": 8.0,
          "category": "venue",
          "visual_intent": "展示训练场地"
        }
      ],
      "highlights": {
        "0": [{"word": "安吉", "category": "location"}],
        "1": [{"word": "补训费", "category": "price"}]
      }
    }
    ```"""
    cues = parse_cue_sheet(raw)
    assert len(cues) == 1
    assert hasattr(cues, "highlights")
    assert cues.highlights == {
        "0": [{"word": "安吉", "category": "location"}],
        "1": [{"word": "补训费", "category": "price"}]
    }

def test_generate_fallback_video_title():
    subs = [
        {"corrected_text": "从今年九月份开始"},
        {"corrected_text": "杭州驾校迎来大改革"},
        {"corrected_text": "我们现在学车全部一口价"},
        {"corrected_text": "不收练车费"}
    ]
    title = generate_fallback_video_title(subs)
    assert "杭州驾校" in title
    assert "学车全部一口价" in title

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

    assert 0.58 <= round(coverage_ratio, 3) <= 0.72, f"空镜覆盖率应达到 60%~70%，当前覆盖时长 {total_broll_seconds:.1f}s ({coverage_ratio:.1%})"
    # 验证开场 1.8s 绝对没有空镜
    assert not any(w["start_time"] < 1.8 for w in windows), "开场 1.8s 真人出镜保护被侵犯"
    # 验证单镜时长都在 2.0s ~ 6.0s 之间
    for w in windows:
        dur = w["end_time"] - w["start_time"]
        assert dur >= 1.8, f"单镜时长过短，存在频闪: {dur}s"
        assert dur <= 6.5, f"单镜时长过长: {dur}s"

    # 验证相邻分镜之间不存在 0.x 秒的闪切主画面（必须要么是0秒连切，要么真人说满一整句 >= 1.8s）
    for i in range(len(windows) - 1):
        gap = round(windows[i + 1]["start_time"] - windows[i]["end_time"], 3)
        assert gap == 0.0 or gap >= 1.8, f"存在瞬间闪跳主画面不良体验: window {i} 与 {i+1} 间隔 {gap}s"

def test_no_flash_cuts_and_sentence_aligned_pacing():
    """测试分镜规划杜绝 0.x 秒主画面瞬间跳转，支持空镜连切并对齐整句/半句"""
    subtitles = [
        {"id": "s0", "start_time": 1.6, "end_time": 4.58, "raw_text": "在湖州学车这三种驾校千万不要报"},
        {"id": "s1", "start_time": 4.94, "end_time": 8.52, "raw_text": "我是小陈在湖州呢已经带过上千个学员"},
        {"id": "s2", "start_time": 8.84, "end_time": 11.16, "raw_text": "四年的时间呢看过太多人踩坑"},
        {"id": "s3", "start_time": 11.44, "end_time": 13.8, "raw_text": "大家看到网上数不胜数的避雷帖"},
        {"id": "s4", "start_time": 14.08, "end_time": 17.72, "raw_text": "就知道现在很多踩坑的原因是什么"},
        {"id": "s5", "start_time": 18.06, "end_time": 21.7, "raw_text": "第一个有三种驾校再便宜咱们也不要去"},
        {"id": "s6", "start_time": 21.92, "end_time": 24.0, "raw_text": "一种呢是价格低到离谱的"},
        {"id": "s7", "start_time": 24.3, "end_time": 27.18, "raw_text": "别人正常报名呢给你三千多两千多"},
        {"id": "s8", "start_time": 27.4, "end_time": 28.76, "raw_text": "他给你报一千多"},
        {"id": "s9", "start_time": 29.02, "end_time": 30.94, "raw_text": "还跟你说全包或者是怎么样"},
    ]
    total_duration = 31.0
    cues = [
        BrollCueItem(start_time=1.8, end_time=6.5, category=MaterialCategory.VENUE, visual_intent="场地"),
        BrollCueItem(start_time=7.0, end_time=11.5, category=MaterialCategory.LESSON, visual_intent="教学"),
    ]
    windows = plan_dual_layer_broll(
        subtitles=subtitles,
        cues=cues,
        total_duration=total_duration,
        target_coverage=0.65,
        available_categories=[MaterialCategory.VENUE, MaterialCategory.LESSON, MaterialCategory.EXPERIENCE]
    )

    # 1. 验证没有出现 0.01s ~ 1.79s 的闪退闪入
    for i in range(len(windows) - 1):
        gap = round(windows[i + 1]["start_time"] - windows[i]["end_time"], 3)
        assert gap == 0.0 or gap >= 1.8, f"分镜 {i} 和 {i+1} 之间存在闪跳: gap={gap}s"

    # 2. 验证成功缝合临近分镜实现空镜连切（gap == 0.0）
    has_continuous_cut = any(
        round(windows[i + 1]["start_time"] - windows[i]["end_time"], 3) == 0.0
        for i in range(len(windows) - 1)
    )
    assert has_continuous_cut, "未能成功缝合临近分镜实现空镜连切"

    # 3. 验证切分时间点均对齐在整句或自然半句附近
    all_sent_points = set()
    for s in subtitles:
        all_sent_points.add(round(s["start_time"], 2))
        all_sent_points.add(round(s["end_time"], 2))
    all_sent_points.add(1.8)

    for w in windows:
        assert any(abs(w["start_time"] - p) <= 0.35 for p in all_sent_points), f"分镜起点 {w['start_time']} 未对齐句子"


def test_snap_cues_to_sentence_and_clause_boundaries():
    """测试时间戳吸附：优先整句起止点，其次逗号子句点"""
    from app.native_engine.scene_decision import snap_cues_to_words
    subtitles = [
        {
            "id": "s1",
            "start_time": 2.0,
            "end_time": 6.0,
            "raw_text": "在杭州学车只要两千多，科目二一把过。",
            "words": [
                {"word": "在杭州", "start": 2.0, "end": 2.5},
                {"word": "学车", "start": 2.5, "end": 3.0},
                {"word": "只要两千多，", "start": 3.0, "end": 4.2},
                {"word": "科目二", "start": 4.3, "end": 5.0},
                {"word": "一把过。", "start": 5.0, "end": 6.0},
            ]
        }
    ]

    # cue 接近句子起点 2.0s (例如 2.2s)，应精准吸附到整句起点 2.0s
    cue1 = [BrollCueItem(start_time=2.2, end_time=5.8, category=MaterialCategory.VENUE, visual_intent="测试")]
    snapped1 = snap_cues_to_words(subtitles, cue1)
    assert snapped1[0].start_time == 2.0
    assert snapped1[0].end_time == 6.0

    # cue 接近逗号停顿点 4.2s (例如 4.3s)，应吸附到逗号处 4.2s 附近
    cue2 = [BrollCueItem(start_time=4.3, end_time=6.0, category=MaterialCategory.LESSON, visual_intent="测试")]
    snapped2 = snap_cues_to_words(subtitles, cue2)
    assert abs(snapped2[0].start_time - 4.2) <= 0.15


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

    # 验证蓝底地名 38BDF8 -> ASS BGR &H00F8BD38&
    assert "F8BD38" in ass_content
    # 验证红底价格 EF4444 -> ASS BGR &H004444EF&
    assert "4444EF" in ass_content
    # 验证纯白高亮 FFFFFF -> ASS BGR &H00FFFFFF&
    assert "FFFFFF" in ass_content


def test_opening_hook_strict_protection_on_compact_timeline():
    """测试重构后的紧凑时间轴：0.0s~1.8s 严格开场真人保护，绝对不出现任何空镜；覆盖率以成片紧凑时长收敛"""
    # 模拟经过粗剪重投影后的紧凑成片字幕（首句从 0.1s 起跑，总片长 21.0s）
    compact_subs = [
        {"id": "s1", "start_time": 0.10, "end_time": 2.20, "corrected_text": "湖州驾校现在大改革"},
        {"id": "s2", "start_time": 2.40, "end_time": 6.50, "corrected_text": "带大家看下我们自建的五万平训练场"},
        {"id": "s3", "start_time": 6.80, "end_time": 12.0, "corrected_text": "倒车入库一把过，重点看准这根线"},
        {"id": "s4", "start_time": 12.2, "end_time": 17.5, "corrected_text": "全包一口价只要两千多，绝无隐形消费"},
        {"id": "s5", "start_time": 17.8, "end_time": 21.0, "corrected_text": "想学车的朋友评论区找我聊"}
    ]

    # 模拟大模型试图在 0.5s 或 1.2s 插入空镜
    cues = [
        BrollCueItem(start_time=0.5, end_time=3.5, category=MaterialCategory.VENUE, visual_intent="门面"),
        BrollCueItem(start_time=1.2, end_time=5.0, category=MaterialCategory.LESSON, visual_intent="教学"),
        BrollCueItem(start_time=7.0, end_time=11.0, category=MaterialCategory.EXPERIENCE, visual_intent="练车"),
    ]

    eff_duration = 21.0
    windows = plan_dual_layer_broll(
        subtitles=compact_subs,
        cues=cues,
        total_duration=eff_duration,
        target_coverage=0.65
    )

    # 1. 核心铁律：所有窗口的 start_time 必须 >= 1.8s
    for w in windows:
        assert w["start_time"] >= 1.8, f"分镜违背 1.8s 开场禁切红线: {w}"

    # 2. 覆盖率收敛：以 21s 真实成片时长规划，总空镜时长不得超标 (不超过 70%)
    total_broll_sec = sum(w["end_time"] - w["start_time"] for w in windows)
    coverage = total_broll_sec / eff_duration
    assert round(coverage, 2) <= 0.70, f"空镜覆盖率超标: {coverage:.1%} > 70%"
    assert coverage >= 0.40, f"空镜覆盖率过低: {coverage:.1%} < 40%"


