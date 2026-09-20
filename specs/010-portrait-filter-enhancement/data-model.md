# Data Model: 真实人物口播视频滤镜画质调优 (portrait-filter-enhancement)

**Feature Branch**: `010-portrait-filter-enhancement`  
**Date**: 2026-09-21

---

## 1. 核心实体模型扩展

### 1.1 EditingStrategy 扩展字段
在工程策略对象 `EditingStrategy`（位于 `backend/app/models/entities.py`）中新增滤镜调优字段：

```python
class FilterPresetType(str, Enum):
    CLEAN_NATURAL = "clean_natural"   # 自然通透 (推荐)
    CRISP_HD = "crisp_hd"             # 质感超清
    WARM_RADIANT = "warm_radiant"     # 元气暖肤
    ORIGINAL = "original"             # 原始原色 (无滤镜)

class EditingStrategy(BaseModel):
    # ... 已有字段保持不变 ...

    # 010: 真实人物口播画面滤镜与调优
    filter_preset: str = "clean_natural"     # 默认选用行业黄金预设：自然通透
    filter_strength: float = 1.0            # 滤镜强度 (0.0 ~ 1.0，默认 1.0，0.0 为完全无额外调色)
```

---

## 2. 预设参数与 FFmpeg 滤镜映射数据结构 (FilterPresetConfig)

内部滤镜映射数据模型（位于 `backend/app/native_engine/ffmpeg_filter.py`）：

```python
@dataclass
class FilterPresetParams:
    name: str
    description: str
    smartblur_lr: float         # luma radius (0.1 ~ 5.0)
    smartblur_ls: float         # luma strength (0.0 ~ 1.0)
    smartblur_lt: float         # luma threshold (-30 ~ 0, 负值表示低对比平坦区平滑)
    eq_contrast: float          # 对比度增益 (基准 1.0)
    eq_brightness: float        # 亮度增益 (基准 0.0)
    eq_saturation: float        # 饱和度增益 (基准 1.0)
    eq_gamma: float             # 中间调提亮 (基准 1.0)
    eq_gamma_r: float = 1.0     # 红色通道 Gamma 微调 (基准 1.0)
    eq_gamma_b: float = 1.0     # 蓝色通道 Gamma 微调 (基准 1.0)
    cas_strength: float = 0.30  # 对比度自适应锐化强度 (0.0 ~ 1.0)
```

### 预设注册表 (PORTRAIT_PRESETS)
```python
PORTRAIT_PRESETS: Dict[str, Optional[FilterPresetParams]] = {
    "clean_natural": FilterPresetParams(
        name="自然通透",
        description="面部暗沉驱散，皮肤质感自然白皙，发丝与眼神光清晰，适合日常手机口播",
        smartblur_lr=1.0, smartblur_ls=0.25, smartblur_lt=-3.5,
        eq_contrast=1.04, eq_brightness=0.02, eq_saturation=1.06, eq_gamma=1.03,
        cas_strength=0.30
    ),
    "crisp_hd": FilterPresetParams(
        name="质感超清",
        description="边缘轮廓极其立体硬朗，抗二次压缩能力最强，适合商单讲解与高质感需求",
        smartblur_lr=0.8, smartblur_ls=0.15, smartblur_lt=-3.0,
        eq_contrast=1.06, eq_brightness=0.01, eq_saturation=1.04, eq_gamma=1.01,
        cas_strength=0.40
    ),
    "warm_radiant": FilterPresetParams(
        name="元气暖肤",
        description="微升色温，面颊红润通透，改善苍白疲惫或冷光灯泛青泛灰",
        smartblur_lr=1.2, smartblur_ls=0.30, smartblur_lt=-4.0,
        eq_contrast=1.03, eq_brightness=0.03, eq_saturation=1.08, eq_gamma=1.04,
        eq_gamma_r=1.02, eq_gamma_b=0.98,
        cas_strength=0.25
    ),
    "original": None  # Bypass: 完全无滤镜处理
}
```

---

## 3. 滤镜链动态组装算法 (Filter Chain Composition Logic)

给定 `preset_key` 和 `strength`（0.0 ~ 1.0），生成 FFmpeg 滤镜子串：
- 若 `preset_key == "original"` 或 `strength <= 0.01`：返回空字符串（Bypass）。
- 参数强度线性插值：
  - `eff_contrast = 1.0 + (params.eq_contrast - 1.0) * strength`
  - `eff_brightness = 0.0 + (params.eq_brightness - 0.0) * strength`
  - `eff_saturation = 1.0 + (params.eq_saturation - 1.0) * strength`
  - `eff_gamma = 1.0 + (params.eq_gamma - 1.0) * strength`
  - `eff_cas = params.cas_strength * strength`
  - `eff_blur_ls = params.smartblur_ls * strength`
- 滤镜链顺序（放置于 `scale` 之后、`pad` 居中补黑边之前）：
  ```text
  scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos+accurate_rnd,
  smartblur=lr={lr:.2f}:ls={eff_blur_ls:.2f}:lt={lt:.2f},
  eq=contrast={eff_contrast:.3f}:brightness={eff_brightness:.3f}:saturation={eff_saturation:.3f}:gamma={eff_gamma:.3f}:gamma_r={eff_gamma_r:.3f}:gamma_b={eff_gamma_b:.3f},
  cas={eff_cas:.2f},
  pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black
  ```
- 降级保护：若本地 FFmpeg 不支持 `cas`（通常极老版本），安全回退为 `unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount={eff_cas:.2f}:chroma_amount=0.0`。
