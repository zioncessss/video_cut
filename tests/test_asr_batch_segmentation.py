import pytest
import re
from typing import List, Dict, Any
from app.native_engine.asr_runner import asr_runner, is_breaking_inseparable_word

# 真实驾考/短视频口播场景测试文案库（涵盖超长句、术语句、连词句、口癖句、碎片句、排比句等）
BATCH_TEST_CASES = [
    {
        "id": "CASE_01_LONG_OVERALL",
        "category": "超长避坑口播",
        "raw_text": "很多外地学员来我们这边学车总担心教练中途会乱收费或者有什么隐形消费其实咱们全包班是没有任何额外费用的",
        "description": "48字连贯超长句，无任何标点，测试自然意群切分与长度控制"
    },
    {
        "id": "CASE_02_INSEPARABLE_TERMS",
        "category": "科目二倒车入库",
        "raw_text": "科目二倒车入库一定要看准后视镜下沿跟控制线重合的时候方向盘直接向右打死",
        "description": "35字实操技巧句，包含'科目二'、'倒车入库'等固定专有术语，测试术语不可拆分性"
    },
    {
        "id": "CASE_03_DANGLING_CONJUNCTION",
        "category": "连词与介词防线",
        "raw_text": "我们训练场不仅有遮阳大棚而且还有冷暖空调和自动挡模拟机供大家免费练习",
        "description": "34字并列句，测试'而且'、'和'等弱连词是否会悬挂在前半句末尾（防'和'挂尾）"
    },
    {
        "id": "CASE_04_PRICE_AND_RULES",
        "category": "费用规则密集句",
        "raw_text": "现在全包只要两千八百八十元从科目一到科目四所有的补考费和模拟费全部包含在内",
        "description": "38字费用说明句，包含'补考费'、'模拟费'、'科目一到科目四'等密集数字与规约"
    },
    {
        "id": "CASE_05_FILLER_PARTICLES",
        "category": "口头禅与助词清洗",
        "raw_text": "那个就是说如果是零基础学员的话呢不用紧张我们都是手把手教学的呀",
        "description": "31字带口语口癖，测试'那个就是说'、'的话呢'、'的呀'等口语助词的清洗与断句"
    },
    {
        "id": "CASE_06_PUNCTUATION_CLAUSES",
        "category": "碎片与逗号复合句",
        "raw_text": "想学车的抓紧了，现在报名下周就能练车，下个月直接拿证回家过年。",
        "description": "30字逗号分句，测试带有标点符号时的节奏保留与标点切分"
    },
    {
        "id": "CASE_07_DRIVING_ACTION_STREAM",
        "category": "科目三路考操作流",
        "raw_text": "上车先系好安全带调整后视镜踩离合挂一挡打左转向灯看后视镜鸣笛松手刹起步",
        "description": "36字紧凑动作流口播，测试紧凑动宾短语的意群切分节奏"
    },
    {
        "id": "CASE_08_PARALLEL_STRUCTURE",
        "category": "排比承诺句",
        "raw_text": "第一不用自己买模拟学时第二教练绝不吃拿卡要第三练车时间自由预约随到随学",
        "description": "36字排比句，包含'第一'、'第二'、'第三'引导词，测试序号引导词切分"
    },
    {
        "id": "CASE_09_QUESTION_AND_CTA",
        "category": "设问与互动呼吁",
        "raw_text": "你们觉得这种收费模式靠谱吗不妨在评论区打出你的城市我们来帮你避雷",
        "description": "32字短视频转场互动句，测试疑问语气与呼吁词'不妨'、'评论区'聚合"
    },
    {
        "id": "CASE_10_HILL_START_TECHNIQUE",
        "category": "半坡起步技巧",
        "raw_text": "半坡起步切记离合器一定要慢抬感受到车身明显抖动的时候再稳住离合慢松刹车",
        "description": "36字控车操作技巧句，包含'半坡起步'、'离合器'等关键控制点"
    },
    {
        "id": "CASE_11_CONTRAST_PITCH",
        "category": "对比营销话术",
        "raw_text": "传统驾校报名便宜但是后期加项收费特别多不如一次性报全包班省心省力",
        "description": "33字对比句，包含'但是'、'不如'等转折对比词"
    },
    {
        "id": "CASE_12_SHORT_FRAGMENTS",
        "category": "微短跳跃碎片流",
        "raw_text": "来看场地。今天天气好。练车的人很多。科目二通过率很高。",
        "description": "27字极短并列句，测试微短句是否会过于细碎闪烁或能够恰当平滑合并"
    },
    {
        "id": "CASE_13_CTA_UNDERSTAND_LEAVE_MESSAGE",
        "category": "转场互动与不可分词防线",
        "raw_text": "想要了解的可以评论区留言哦",
        "description": "14字典型短视频结尾互动引导，包含'了解'、'评论区'、'留言'等，测试14字单句完整性，绝不可在'想要了/解'切断"
    }
]


def simulate_words_from_text(text: str, wpm: int = 240) -> List[Dict[str, Any]]:
    """模拟真实 ASR 返回的逐字时间戳序列（根据平均语速估算）"""
    words = []
    curr_t = 1.0
    sec_per_char = 60.0 / wpm
    clean_text = re.sub(r'[,，;；!！?？。、\s]', '', text)
    for ch in clean_text:
        ch_end = round(curr_t + sec_per_char, 3)
        words.append({
            "word": ch,
            "start": round(curr_t, 3),
            "end": ch_end
        })
        curr_t = ch_end
    return words


def run_pipeline(raw_text: str, use_words: bool = True) -> List[Dict[str, Any]]:
    """执行后端完整的 ASR 拆分与平滑合并管道"""
    total_dur = len(raw_text) * 0.25
    candidate_sub = {
        "id": "test_seg_0",
        "start_time": 0.0,
        "end_time": round(total_dur, 2),
        "raw_text": raw_text,
        "corrected_text": raw_text,
    }
    if use_words:
        candidate_sub["words"] = simulate_words_from_text(raw_text)

    # 1. 过滤语气停顿与清洗口癖
    valid = asr_runner.filter_filler_segments([candidate_sub])
    valid = asr_runner.clean_filler_particles(valid)
    if not valid:
        return []

    # 2. 黄金自然句切分 (max_chars=15, soft_max=15, min_chunk=4)
    split_res = asr_runner.split_into_readable_segments(
        valid,
        max_chars=15,
        soft_max=15,
        min_chunk=4
    )

    # 3. 全局跨句碎片平滑合并 (min_chars=4, max_chars=15)
    merged_res = asr_runner.merge_short_segments(
        split_res,
        min_chars=4,
        min_duration=1.0,
        max_chars=15,
        max_gap=0.55
    )
    return merged_res


def evaluate_segmentation(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """多维度严苛评测分段质量"""
    issues = []
    lengths = []
    
    # 挂尾禁绝词（弱连词、介词挂尾）
    DANGLING = ("和", "与", "跟", "及", "同", "在", "从", "到", "向", "由", "把", "被", "让")

    for idx, s in enumerate(segments):
        txt = s.get("corrected_text") or s.get("raw_text", "")
        l = len(txt)
        lengths.append(l)

        # 检查 1：字数超长导致折行
        if l > 16:
            issues.append(f"第 {idx+1} 段超长 ({l}字 > 16字，短视频竖屏易折行): '{txt}'")

        # 检查 2：单字或微短孤立碎片闪烁
        if l < 3:
            issues.append(f"第 {idx+1} 段过短 (<3字孤立闪烁): '{txt}'")

        # 检查 3：连词挂尾
        if any(txt.endswith(d) for d in DANGLING):
            issues.append(f"第 {idx+1} 段连词挂尾: '{txt}'")

        # 检查 4：跨段破坏不可分词
        if idx < len(segments) - 1:
            next_txt = segments[idx+1].get("corrected_text") or segments[idx+1].get("raw_text", "")
            if is_breaking_inseparable_word(txt, next_txt):
                issues.append(f"第 {idx+1} 与第 {idx+2} 段之间斩断了不可分词: '{txt}' | '{next_txt}'")

    return {
        "count": len(segments),
        "lengths": lengths,
        "min_len": min(lengths) if lengths else 0,
        "max_len": max(lengths) if lengths else 0,
        "avg_len": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "issues": issues,
        "is_healthy": len(issues) == 0
    }


def test_batch_subtitle_segmentation():
    """批量测试所有典型用例的切分结果与舒适度指标"""
    print("\n" + "="*80)
    print("【短视频口播字幕 ASR 拆分与视读舒适度批量测试】")
    print("="*80)

    total_cases = len(BATCH_TEST_CASES)
    passed_cases = 0

    for idx, case in enumerate(BATCH_TEST_CASES):
        raw_text = case["raw_text"]
        
        # 分别测试模式 A (带物理词时间戳) 和模式 B (无词级时间戳标点意群切分)
        segs_a = run_pipeline(raw_text, use_words=True)
        eval_a = evaluate_segmentation(segs_a)

        segs_b = run_pipeline(raw_text, use_words=False)
        eval_b = evaluate_segmentation(segs_b)

        is_passed = eval_a["is_healthy"] and eval_b["is_healthy"]
        if is_passed:
            passed_cases += 1

        print(f"\n用例 {idx+1}/{total_cases}: [{case['category']}] {case['id']}")
        print(f"  原始文本 ({len(raw_text)}字): {raw_text}")
        print(f"  模式 A (带词级时间戳): 切分为 {eval_a['count']} 段, 字数分布 {eval_a['lengths']} (均长 {eval_a['avg_len']})")
        for i, s in enumerate(segs_a):
            t = s.get("corrected_text") or s.get("raw_text")
            print(f"     [{i+1}] ({len(t)}字) {t}")
        if eval_a["issues"]:
            print(f"     ⚠️ 模式 A 发现问题: {', '.join(eval_a['issues'])}")

        print(f"  模式 B (纯文本标点/意群切分): 切分为 {eval_b['count']} 段, 字数分布 {eval_b['lengths']} (均长 {eval_b['avg_len']})")
        for i, s in enumerate(segs_b):
            t = s.get("corrected_text") or s.get("raw_text")
            print(f"     [{i+1}] ({len(t)}字) {t}")
        if eval_b["issues"]:
            print(f"     ⚠️ 模式 B 发现问题: {', '.join(eval_b['issues'])}")

    print("\n" + "="*80)
    print(f"测试汇总: 总共 {total_cases} 个场景，通过 {passed_cases} 个，健康率: {passed_cases/total_cases*100:.1f}%")
    print("="*80)

    assert passed_cases >= total_cases * 0.8, f"合格率低于 80%: {passed_cases}/{total_cases}"
