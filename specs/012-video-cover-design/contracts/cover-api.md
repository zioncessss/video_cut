# Phase 1: 接口契约设计 (Interface Contracts - Enhanced)

**Feature**: 视频封面设计与模板导出优化 (`012-video-cover-design`)  
**Created**: 2026-09-21  
**Status**: Approved

---

## 1. 封面模板元数据查询

### `GET /api/v1/editor/cover-templates`
获取系统预置的 6 款实操短视频口播封面模板列表与 4 套精选调色盘。

#### Response
```json
{
  "code": 0,
  "data": {
    "templates": [
      {
        "id": "sticker_double_stroke",
        "name": "双层描边贴纸大字",
        "category": "local_hook",
        "badge": "👑 爆款首选",
        "sample_preview": "武义学车款",
        "description": "顶部超大双层描边（黑描边+纯白贴纸厚边），底部手势指示胶囊与荧光引导字",
        "supported_themes": ["neon_cyber", "authority_red", "hot_pink_gold"]
      },
      {
        "id": "split_contrast_bar",
        "name": "上下通栏权威撞色条",
        "category": "authority_banner",
        "badge": "🏛️ 权威正规",
        "sample_preview": "杭州学车款",
        "description": "顶部全宽红底横条白字，中间人物实景，底部全宽白底横条深红大字痛点",
        "supported_themes": ["authority_red", "frost_burgundy"]
      },
      {
        "id": "rainbow_arc_header",
        "name": "拱形包头彩虹字",
        "category": "curved_impact",
        "badge": "⚡ 同城爆款",
        "sample_preview": "金华金东款",
        "description": "向上彩虹拱形包头弧字，不挡人脸环抱发顶，配手写疑问句与斜角账号标",
        "supported_themes": ["hot_pink_gold", "neon_cyber"]
      },
      {
        "id": "bottom_fog_vignette",
        "name": "胸前羽化白光沉浸字",
        "category": "vignette_focus",
        "badge": "✨ 高级清透",
        "sample_preview": "婺城学车款",
        "description": "底部柔和白色羽化遮罩自然弱化杂乱环境，胸前排布立体深红白边特大字",
        "supported_themes": ["frost_burgundy", "authority_red"]
      },
      {
        "id": "angled_impact_stamp",
        "name": "倾角冲击引流标",
        "category": "angled_stamp",
        "badge": "💥 强烈冲击",
        "sample_preview": "绍兴学车款",
        "description": "顶部 -10° 动感微倾斜大字贴纸，右侧双行紧凑金句，底部实色警示横条",
        "supported_themes": ["authority_red", "hot_pink_gold"]
      },
      {
        "id": "clean_editorial",
        "name": "极简轻奢杂志风",
        "category": "editorial",
        "badge": "📖 知性轻奢",
        "sample_preview": "小红书爆款",
        "description": "轻奢英文章节标、纤细纯白大字、细横线与衬线副标，高级留白",
        "supported_themes": ["frost_burgundy"]
      }
    ],
    "palettes": [
      {"id": "authority_red", "name": "国潮权威红", "main": "#B91C1C", "sub": "#FFFFFF", "accent": "#0F172A"},
      {"id": "neon_cyber", "name": "电光冷紫绿", "main": "#A5B4FC", "sub": "#86EFAC", "accent": "#000000"},
      {"id": "hot_pink_gold", "name": "荧光粉金", "main": "#F43F5E", "sub": "#FACC15", "accent": "#111827"},
      {"id": "frost_burgundy", "name": "雪白羽化酒红", "main": "#991B1B", "sub": "#FFFFFF", "accent": "#FDE047"}
    ],
    "safe_zones": {
      "douyin": {"top": 0.05, "bottom": 0.18, "left": 0.05, "right": 0.15},
      "xiaohongshu": {"aspect": "3:4", "top": 0.125, "bottom": 0.125, "left": 0.0, "right": 0.0}
    }
  }
}
```

---

## 2. 封面配置保存与高清合成

### `POST /api/v1/projects/{project_id}/cover`
保存封面配置并即时合成 1080x1920 高清封面图。

#### Request Body
```json
{
  "source": "video_frame",
  "frame_timestamp": 0.5,
  "template_id": "sticker_double_stroke",
  "location_tag": "武义学车",
  "main_title": "场地培训练车全包含",
  "sub_title": "先看这个",
  "color_theme": "neon_cyber",
  "aspect_mode": "blur_padding",
  "show_safe_zone": false,
  "zone_styles": {
    "location": {"text_color": "#2E7CD6", "stroke_color": "#FFFFFF", "scale": 1.2, "offset_y": -0.03},
    "main": {"text_color": "#FFFFFF", "stroke_color": "#000000", "scale": 1.0, "offset_y": 0.05},
    "sub": {}
  }
}
```

#### `zone_styles` [R3 新增]
按文字区域覆盖样式；缺省 key 或缺省字段 = 跟随模板与调色盘默认。

| 字段 | 类型 | 约束 | 说明 |
| :--- | :--- | :--- | :--- |
| `text_color` | string? | `^#[0-9A-Fa-f]{6}$` | 文字填充色覆盖（候选色板：调色盘 main/sub/accent + `#FFFFFF` + `#000000`） |
| `stroke_color` | string? | `^#[0-9A-Fa-f]{6}$` | 文字描边色覆盖 |
| `scale` | number | clamp [0.6, 1.4] | 字号缩放倍率 |
| `offset_y` | number | clamp [-0.12, 0.12] | 纵向偏移（画布高度占比，正值下移） |

合法 key：`location`（地域区）/ `main`（主标题钩子区）/ `sub`（副标题区）。非法 key、非法颜色格式返回 422；越界数值由服务端 clamp 后持久化。

#### Response
```json
{
  "code": 0,
  "message": "封面保存并生成成功",
  "data": {
    "cover_image_path": "storage/tasks/task_20260921_120000_th_001/cover.jpg",
    "cover_source": "video_frame",
    "cover_url": "/storage/tasks/task_20260921_120000_th_001/cover.jpg",
    "cover_config": {
      "template_id": "sticker_double_stroke",
      "location_tag": "武义学车",
      "main_title": "场地培训练车全包含",
      "sub_title": "先看这个",
      "color_theme": "neon_cyber"
    }
  }
}
```
