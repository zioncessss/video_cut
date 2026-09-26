# Phase 1: 数据模型与实体设计 (Data Model - Enhanced)

**Feature**: 视频封面设计与模板导出优化 (`012-video-cover-design`)  
**Created**: 2026-09-21  
**Status**: Approved

---

## 1. 实体定义与字段结构

### 1.1 封面设计配置实体 (`CoverDesignConfig`)
表示针对一个剪辑工程所定制的封面样式、底图与排版配置：

```python
class CoverDesignConfig(BaseModel):
    source: Literal["video_frame", "custom_upload"] = "video_frame"
    frame_timestamp: float = 0.0            # 截帧时间点（秒）
    custom_image_path: Optional[str] = None # 自定义上传图片的磁盘相对路径
    
    # 6 大实战高转化模板
    template_id: Literal[
        "sticker_double_stroke", # 双层描边贴纸大字 (武义学车样张)
        "split_contrast_bar",    # 上下通栏权威撞色条 (杭州学车样张)
        "rainbow_arc_header",    # 拱形包头彩虹字 (金华金东学车样张)
        "bottom_fog_vignette",   # 胸前羽化白光沉浸字 (婺城学车样张)
        "angled_impact_stamp",   # 倾角冲击引流标 (绍兴学车样张)
        "clean_editorial",       # 极简轻奢杂志风 (知性小红书样张)
        "gold_bold",             # 兼容原大字报
        "color_badge",           # 兼容原色块标
        "dual_contrast"          # 兼容原双色
    ] = "sticker_double_stroke"

    # 文案分层结构
    location_tag: str = ""                  # [NEW] 核心地域词（如“武义”、“杭州”、“金东”、“婺城”、“绍兴”）
    main_title: str = ""                    # 封面主标题（建议 4~10 字吸睛大字）
    sub_title: str = ""                     # 封面副标题/痛点说明（建议 4~12 字）
    
    # 视觉调色与排版
    color_theme: Literal[
        "authority_red",   # 国潮权威红 (红白黑权威大校感)
        "neon_cyber",      # 电光冷紫绿 (年轻潮酷贴纸感)
        "hot_pink_gold",   # 荧光粉金 (价格避坑揭秘感)
        "frost_burgundy"   # 雪白羽化酒红 (清透高级实景感)
    ] = "authority_red"

    font_family: Literal["heavy_gothic", "brush_kai", "handwriting_tilt", "editorial_serif"] = "heavy_gothic"
    aspect_mode: Literal["blur_padding", "center_crop"] = "blur_padding" # 上传图片适配模式
    show_safe_zone: bool = True             # 编辑态是否展示平台安全区视框 (抖音/小红书)

    # [R3] 分区文本样式覆盖：key ∈ {"location", "main", "sub"}；缺省 = 完全跟随模板与调色盘默认
    zone_styles: Dict[str, "CoverTextZoneStyle"] = Field(default_factory=dict)


### 1.1.1 分区文本样式实体 (`CoverTextZoneStyle`) [R3 新增]

每个文字区域的可覆盖样式；所有字段可选，None/中性值表示跟随模板与调色盘默认：

```python
class CoverTextZoneStyle(BaseModel):
    text_color: Optional[str] = None    # 文字填充色 (#RRGGBB)，覆盖调色盘 main/模板默认
    stroke_color: Optional[str] = None  # 文字描边色 (#RRGGBB)，覆盖描边默认
    scale: float = 1.0                  # 字号缩放，clamp [0.6, 1.4]
    offset_y: float = 0.0               # 纵向偏移（占画布高度比例），clamp [-0.12, 0.12]

# 渲染取色三级优先级：分区覆盖 → 模板默认 → 调色盘
# 颜色候选色板（前端）：当前调色盘 main / sub / accent + 纯白 #FFFFFF + 纯黑 #000000
# 校验规则：颜色必须匹配 ^#[0-9A-Fa-f]{6}$；scale/offset_y 由渲染端与前端双向 clamp
```

**三个区域与模板文字元素的映射**：
| zone key | 含义 | 默认位置 | 模板元素对应 |
| :--- | :--- | :--- | :--- |
| `location` | 地域大字（顶部） | 8%~20% 高 | sticker 顶部贴纸字 / split 顶部通栏字 / arc 拱形字 / fog 大字 / angled 倾斜贴纸 / editorial 主标（无地域词时） |
| `main` | 主标题钩子（中部） | 55%~72% 高 | sticker 手写钩子 / split 底部通栏大字 / arc 手写疑问句 / fog 大字（无地域词时）/ angled 右侧金句 / editorial 主标 |
| `sub` | 副标题/标签 | 74%~80% 高 | sticker 小标签 / split 灰色小字 / arc 右上胶囊 / fog 顶部倾斜副标 / angled 警示通栏 / editorial 衬线副标 |
```

### 1.2 AI 推荐封面文案实体 (`SuggestedCoverTitle`)
剪辑阶段由大模型根据全篇口播痛点与地域伴随提炼的候选爆款标题：

```python
class SuggestedCoverTitle(BaseModel):
    location_tag: Optional[str] = None     # 提取到的地域地名（如“武义学车”）
    title: str                             # 主标题（直击痛点的大字文案）
    sub_title: Optional[str] = None        # 副标题（背书、细节或胶囊标签）
    rationale: Optional[str] = None        # 爆款推荐理由
    style: Optional[str] = None            # 推荐搭配的视觉模板
```

> **[R3] 分区推荐语义**：一组 `SuggestedCoverTitle` 即三个文字区域的一组候选——
> `location_tag` → 地域区候选、`title`/`main_title` → 主标题区候选、`sub_title` → 副标题区候选。
> 2~3 组文案在前端按区展开为每区 2~3 个推荐 chips。
> AI 缺失时的按区兜底：地域区=词库地名高亮提取；主标题区=学车特点库（`cover_hooks.hooks`）；
> 副标题区=特点库小标签。保证三个区域始终有可点击的推荐候选。

### 1.3 封面模板预设元数据 (`CoverTemplateMeta`)
描述前端与后端共享的可用模板预设字典：

```python
class CoverTemplateMeta(BaseModel):
    id: str                                # 模板唯一标识
    name: str                              # 模板显示名称 (如 "双层描边贴纸大字")
    category: str                          # 分类: "local_hook" | "authority_banner" | "curved_impact" | "vignette_focus" | "editorial"
    badge: str                             # 标签文案 (如 "👑 爆款首选")
    sample_preview: str                    # 样本参照 (如 "武义学车款")
    description: str                       # 适用场景介绍
    supported_themes: List[str]            # 该模板推荐的配色方案列表
```

---

## 2. 工程主实体扩展 (`CutProject` & `EditingStrategy`)

### 2.1 `CutProject` 扩展字段
在 `backend/app/models/entities.py` 的 `CutProject` 实体中扩展以下持久化字段：

```python
class CutProject(BaseModel):
    cover_image_path: Optional[str] = None         # 最终渲染的高清 cover.jpg 物理相对路径
    cover_source: Optional[str] = "frame"          # 封面底图来源: frame | upload
    cover_config: Optional[CoverDesignConfig] = None # 完整的封面配置元数据
    suggested_cover_titles: List[SuggestedCoverTitle] = Field(default_factory=list) # AI 伴随生成的封面标题建议
```

### 2.2 `EditingStrategy` 导出策略扩展
```python
class EditingStrategy(BaseModel):
    embed_cover_as_first_frame: bool = False # 导出时是否将封面压入视频首帧 (持续 0.08s)
```
