# Quickstart: 真实人物口播滤镜调优验证指南

**Feature**: `010-portrait-filter-enhancement`  
**Date**: 2026-09-21

本文档提供快速验证口播滤镜调优管线的端到端执行命令与预期效果。

---

## 1. 前置条件

1. 本机已安装并就绪 FFmpeg（运行 `ffmpeg -version` 确认可用）。
2. Python 环境已就绪（激活虚拟环境并具备 pytest）。

---

## 2. 自动化单元与集成测试

运行以下测试用例验证滤镜参数组装、边界防御与导出管线：

```bash
# 执行口播滤镜管线专属测试
pytest tests/test_portrait_filters.py -v
```

### 预期验证点：
- [x] `test_filter_presets_registry`: 校验 4 大预设（`clean_natural`, `crisp_hd`, `warm_radiant`, `original`）参数自洽性。
- [x] `test_filter_chain_composition`: 验证插值算法与 FFmpeg 滤镜字符串生成（黑边保护：滤镜在 scale 之后、pad 之前）。
- [x] `test_real_render_with_filter`: 使用真实口播小样视频，验证 `compose_jl_cut` 带入滤镜后能正常完成导出，不产生光晕与色度溢出。
- [x] `test_filter_strength_interpolation`: 验证 50% 强度下的线性衰减插值。
- [x] `test_bypass_on_original`: 验证 `original` 模式下滤镜链路被完全旁路，零额外开销。

---

## 3. 手动直观视觉效果对比验证 (Visual Sanity Check)

运行测试脚本从真实口播素材截取单帧生成对比图：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
python -c "
from pathlib import Path
from app.native_engine.ffmpeg_filter import composer
th_file = list(Path('storage/materials/talking_head').glob('*.mp4'))[0]
print(f'Using material: {th_file}')
# 验证滤镜链生成
f = composer.build_portrait_filter_chain('clean_natural', strength=1.0)
print(f'Generated filter chain: {f}')
"
```

### 预期输出：
```text
Using material: storage/materials/talking_head/...
Generated filter chain: smartblur=lr=1.00:ls=0.25:lt=-3.50,eq=contrast=1.040:brightness=0.020:saturation=1.060:gamma=1.030:gamma_r=1.000:gamma_b=1.000,cas=0.30
```

---

## 4. 端到端工作台操作验证

1. 启动前后端服务（或 Electron 桌面端）。
2. 进入 `/editor` 打开任意口播剪辑工程。
3. 在右侧属性面板找到“画面调优与滤镜”配置卡片。
4. 切换“自然通透”/“质感超清”/“元气暖肤”/“原色”。
5. 点击“立即合成导出”。
6. 查看合成出的成片：画面色彩通透，主播气色红润，眼神光与发丝清晰分明，且无任何白边/噪点放大现象。
