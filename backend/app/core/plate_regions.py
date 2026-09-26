"""
浙江省 11 地市车牌字典、行政区划常识与 ASR 地名智能推导引擎
涵盖 浙A~浙L 11 个地级市、下辖区县、高频考场地名及车牌前缀匹配。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import re


@dataclass(frozen=True)
class ZhejiangRegionInfo:
    code: str              # 统一标准识别码，例如 "浙E·湖州"
    plate_prefix: str      # 车牌字母前缀，例如 "浙E"
    city_name: str         # 地级市中文名，例如 "湖州"
    districts: List[str]   # 下辖区县名
    landmarks: List[str] = field(default_factory=list) # 知名驾考场、考点等关键词


# 浙江 11 地市标准常识库定义
ZHEJIANG_REGIONS: List[ZhejiangRegionInfo] = [
    ZhejiangRegionInfo(
        code="浙A·杭州",
        plate_prefix="浙A",
        city_name="杭州",
        districts=["上城", "下城", "江干", "拱墅", "西湖", "滨江", "萧山", "余杭", "临平", "钱塘", "富阳", "临安", "桐庐", "淳安", "建德"],
        landmarks=["场口考场", "场口", "转塘", "三墩", "下沙", "富阳考场", "良渚"]
    ),
    ZhejiangRegionInfo(
        code="浙B·宁波",
        plate_prefix="浙B",
        city_name="宁波",
        districts=["海曙", "江北", "镇海", "北仑", "鄞州", "奉化", "象山", "宁海", "余姚", "慈溪"],
        landmarks=["横溪考场", "横溪"]
    ),
    ZhejiangRegionInfo(
        code="浙C·温州",
        plate_prefix="浙C",
        city_name="温州",
        districts=["鹿城", "龙湾", "瓯海", "洞头", "瑞安", "乐清", "永嘉", "平阳", "苍南", "文成", "泰顺", "龙港"],
        landmarks=["娄桥考场", "娄桥"]
    ),
    ZhejiangRegionInfo(
        code="浙D·绍兴",
        plate_prefix="浙D",
        city_name="绍兴",
        districts=["越城", "柯桥", "上虞", "诸暨", "嵊州", "新昌"],
        landmarks=["袍江考场", "袍江"]
    ),
    ZhejiangRegionInfo(
        code="浙E·湖州",
        plate_prefix="浙E",
        city_name="湖州",
        districts=["吴兴", "南浔", "德清", "长兴", "安吉"],
        landmarks=["大港考场", "大港", "雉城", "织里"]
    ),
    ZhejiangRegionInfo(
        code="浙F·嘉兴",
        plate_prefix="浙F",
        city_name="嘉兴",
        districts=["南湖", "秀洲", "嘉善", "海盐", "海宁", "平湖", "桐乡"],
        landmarks=["富润考场", "富润"]
    ),
    ZhejiangRegionInfo(
        code="浙G·金华",
        plate_prefix="浙G",
        city_name="金华",
        districts=["婺城", "金东", "兰溪", "义乌", "东阳", "永康", "武义", "浦江", "磐安"],
        landmarks=["白龙桥考场", "白龙桥", "金西考场"]
    ),
    ZhejiangRegionInfo(
        code="浙H·衢州",
        plate_prefix="浙H",
        city_name="衢州",
        districts=["柯城", "衢江", "江山", "常山", "开化", "龙游"],
        landmarks=["西区分中心", "西区考场"]
    ),
    ZhejiangRegionInfo(
        code="浙J·台州",
        plate_prefix="浙J",
        city_name="台州",
        districts=["椒江", "黄岩", "路桥", "临海", "温岭", "玉环", "三门", "天台", "仙居"],
        landmarks=["台州考场", "头门港"]
    ),
    ZhejiangRegionInfo(
        code="浙K·丽水",
        plate_prefix="浙K",
        city_name="丽水",
        districts=["莲都", "龙泉", "青田", "缙云", "遂昌", "松阳", "云和", "庆元", "景宁"],
        landmarks=["水阁考场", "水阁"]
    ),
    ZhejiangRegionInfo(
        code="浙L·舟山",
        plate_prefix="浙L",
        city_name="舟山",
        districts=["定海", "普陀", "岱山", "嵊泗"],
        landmarks=["岑港考场", "岑港", "盐仓"]
    ),
]

REGION_MAP_BY_CODE: Dict[str, ZhejiangRegionInfo] = {r.code: r for r in ZHEJIANG_REGIONS}
REGION_CODES: List[str] = [r.code for r in ZHEJIANG_REGIONS]
DEFAULT_REGION_CODE: str = "浙E·湖州"


def is_valid_zhejiang_region(code: Optional[str]) -> bool:
    """校验是否为合法的浙江省 11 地市代码"""
    if not code:
        return False
    return code in REGION_MAP_BY_CODE


def normalize_region_code(code: Optional[str]) -> Optional[str]:
    """标准化地区代码，如 '浙A' 或 '杭州' 映射为 '浙A·杭州'"""
    if not code:
        return None
    code_strip = code.strip()
    if code_strip in REGION_MAP_BY_CODE:
        return code_strip
    for r in ZHEJIANG_REGIONS:
        if code_strip == r.plate_prefix or code_strip == r.city_name or f"{r.plate_prefix}·{r.city_name}" == code_strip:
            return r.code
        # 兼容中间是空格或短横线的写法，如 "浙A 杭州"
        if code_strip in (f"{r.plate_prefix} {r.city_name}", f"{r.plate_prefix}-{r.city_name}"):
            return r.code
    return None


# 对易产生歧义的区县名（如“三门”易与“三门科目”冲突，“路桥”易与“过路桥费”冲突）施加语境消歧保护
AMBIGUOUS_DISTRICT_PATTERNS: Dict[str, re.Pattern] = {
    "三门": re.compile(r"(?:在|去|到|来|位于|来自)三门|三门(?:县|考场|驾校|学车|练车|教练|交警)"),
    "路桥": re.compile(r"(?:在|去|到|来|位于|来自)路桥|路桥(?:区|考场|驾校|学车|练车|教练)"),
    "江山": re.compile(r"(?:在|去|到|来|位于|来自)江山|江山(?:市|考场|驾校|学车|练车|教练)"),
    "开化": re.compile(r"(?:在|去|到|来|位于|来自)开化|开化(?:县|考场|驾校|学车|练车|教练)"),
    "江北": re.compile(r"(?:在|去|到|来|位于|来自)江北|江北(?:区|考场|驾校|学车|练车|教练)"),
}


def deduce_target_region(subtitles_or_text: Any, default_region: Optional[str] = None) -> Optional[str]:
    """
    根据 ASR 转写字幕或纯文本内容，自动打分推导所属地级市车牌代码。
    若无明确地名提及，回退到 default_region (默认为 None，不强加城市假定)。
    """
    if not subtitles_or_text:
        return default_region

    full_text = ""
    if isinstance(subtitles_or_text, str):
        full_text = subtitles_or_text
    elif isinstance(subtitles_or_text, list):
        parts = []
        for s in subtitles_or_text:
            if isinstance(s, dict):
                parts.append(s.get("corrected_text") or s.get("text") or s.get("raw_text") or "")
            elif hasattr(s, "corrected_text"):
                parts.append(getattr(s, "corrected_text", "") or getattr(s, "raw_text", ""))
            elif isinstance(s, str):
                parts.append(s)
        full_text = " ".join(parts)

    if not full_text:
        return default_region

    scores: Dict[str, int] = {r.code: 0 for r in ZHEJIANG_REGIONS}

    # 驾考与地域强相关上下文触发词
    DRIVING_CONTEXTS = ["学车", "驾校", "考场", "练车", "教练", "考驾照", "拿证", "科目二", "科目三", "体检"]

    for r in ZHEJIANG_REGIONS:
        # 1. 命中具体车牌代码（如 "浙E"），权重最高 (+15)
        plate_pattern = re.compile(rf"\b{re.escape(r.plate_prefix)}\b|{re.escape(r.plate_prefix)}[A-Za-z0-9\u4e00-\u9fa5]")
        if plate_pattern.search(full_text) or r.plate_prefix in full_text:
            scores[r.code] += 15

        # 2. 命中地级市名称（如 "湖州"），权重 (+10)
        city_count = full_text.count(r.city_name)
        if city_count > 0:
            scores[r.code] += city_count * 10
            # 检查是否有地市+驾考组合词（如 "湖州学车"）
            for ctx in DRIVING_CONTEXTS:
                if f"{r.city_name}{ctx}" in full_text:
                    scores[r.code] += 8

        # 3. 命中区县名（如 "长兴", "安吉"），权重 (+6)，多义词消歧防误判
        for dist in r.districts:
            if dist in AMBIGUOUS_DISTRICT_PATTERNS:
                matches = AMBIGUOUS_DISTRICT_PATTERNS[dist].findall(full_text)
                d_count = len(matches)
            else:
                d_count = full_text.count(dist)
            if d_count > 0:
                scores[r.code] += d_count * 6
                for ctx in DRIVING_CONTEXTS:
                    if f"{dist}{ctx}" in full_text:
                        scores[r.code] += 6

        # 4. 命中知名考场或地标（如 "大港考场", "场口"），权重 (+8)
        for lm in r.landmarks:
            if lm in full_text:
                scores[r.code] += 8

    # 找出最高分的城市
    best_region, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score > 0:
        return best_region

    return default_region
