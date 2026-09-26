import pytest
from app.core.plate_regions import deduce_target_region, DEFAULT_REGION_CODE


def test_deduce_by_plate_prefix():
    text = "今天我们来看看浙E牌照的教练车在倒车入库时的点位"
    result = deduce_target_region(text)
    assert result == "浙E·湖州"

    text_a = "浙A牌照教练车统一在杭州场口考场进行测试"
    result_a = deduce_target_region(text_a)
    assert result_a == "浙A·杭州"


def test_deduce_by_city_and_driving_context():
    # 口播提到地级市
    text = "想要在湖州学车的朋友们注意了，科目二千万不要压线"
    result = deduce_target_region(text)
    assert result == "浙E·湖州"

    text_nb = "宁波学车攻略：从体检报名到拿证只需45天"
    result_nb = deduce_target_region(text_nb)
    assert result_nb == "浙B·宁波"


def test_deduce_by_district_and_landmarks():
    # 提到长兴
    text = "我们今天来到长兴大港考场，带大家实地走一趟科目三路线"
    result = deduce_target_region(text)
    assert result == "浙E·湖州"

    # 提到义乌
    text = "义乌考点科目二侧方停车技巧详解"
    result = deduce_target_region(text)
    assert result == "浙G·金华"

    # 提到富阳场口
    text = "场口考场坡道定点停车起步防溜车秘诀"
    result = deduce_target_region(text)
    assert result == "浙A·杭州"


def test_deduce_by_subtitle_segments_list():
    subtitles = [
        {"id": "sub_0", "corrected_text": "同学们好，今天给大家讲讲考驾照流程"},
        {"id": "sub_1", "corrected_text": "特别是在湖州本地报考的小伙伴"},
        {"id": "sub_2", "corrected_text": "安吉和德清的学员可以直接去就近考场"},
    ]
    result = deduce_target_region(subtitles)
    assert result == "浙E·湖州"


def test_deduce_fallback_when_no_city():
    text = "离合器半联动一定要稳住，慢慢抬起，听到发动机声音变沉闷时稳住刹车"
    result = deduce_target_region(text)
    assert result == DEFAULT_REGION_CODE


def test_deduce_polysemy_disambiguation():
    # "三门" 作为量词（"三门科目"），不应被误判为台州
    text_quantifier = "今天带大家复习，咱们科目一、科目二、科目三三门全部一把过！"
    assert deduce_target_region(text_quantifier) == DEFAULT_REGION_CODE

    # "三门" 真实地名语境，准确推导为台州
    text_place = "在三门学车的朋友注意了，一定要提前去考场踩点"
    assert deduce_target_region(text_place) == "浙J·台州"

    text_county = "浙江台州三门县练车基地实况"
    assert deduce_target_region(text_county) == "浙J·台州"

    # "路桥" 作为过路过桥短语，不应误判
    text_bridge = "注意观察路桥接缝和下雨天积水"
    assert deduce_target_region(text_bridge) == DEFAULT_REGION_CODE

    # "路桥" 作为台州路桥区，准确识别
    text_luqiao = "来到台州路桥考场，带大家看下曲线行驶技巧"
    assert deduce_target_region(text_luqiao) == "浙J·台州"
