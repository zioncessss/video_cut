# Phase 1: 快速验证与集成测试指南 (Quickstart - Enhanced)

**Feature**: 视频封面设计与模板导出优化 (`012-video-cover-design`)  
**Created**: 2026-09-21  
**Status**: Approved

---

## 1. 验证目标

本文档用于端到端验证 6 大实战封面设计与同城地域大字特性：
1. **同城地域大字 (Location Hook)**：验证提取与排版“武义”、“杭州”、“金东”、“婺城”、“绍兴”等地域大字；
2. **6 大实战爆款模板渲染**：
   - 双层描边贴纸大字 (`sticker_double_stroke`)
   - 上下通栏权威撞色条 (`split_contrast_bar`)
   - 拱形包头彩虹字 (`rainbow_arc_header`)
   - 胸前羽化白光沉浸字 (`bottom_fog_vignette`)
   - 倾角冲击引流标 (`angled_impact_stamp`)
   - 极简轻奢杂志风 (`clean_editorial`)
3. **4 套高转化调色盘**：国潮权威红、电光冷紫绿、荧光粉金、雪白羽化酒红；
4. **导出直观预览与零转码开销**：在导出弹窗中即时选择与预览，单次压制同步输出 `cover.jpg`。

---

## 2. 自动化测试套件运行

### 2.1 比例适配与模板渲染纯函数测试
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
d:\project\video_cut\.venv\Scripts\python.exe -m pytest tests/test_cover_generator.py -v
```
**期望结果**：
- 6 大模板均能成功渲染 1080x1920 高清图像，RGBA 无失真；
- 双层描边（外层白、中层黑、内层彩）无笔画粘连；
- 拱形文字与倾角计算无溢出。

### 2.2 伴随式 AI 封面文案与地域词提取单测
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
d:\project\video_cut\.venv\Scripts\python.exe -m pytest tests/test_scene_decision_cover_titles.py -v
```
**期望结果**：
- 成功提炼包含地域地名的候选爆款文案。

### 2.3 端到端 API 集成测试
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
d:\project\video_cut\.venv\Scripts\python.exe -m pytest tests/test_cover_pipeline_e2e.py -v
```
**期望结果**：
- `GET /api/v1/editor/cover-templates` 返回 6 款模板预设；
- `POST /api/v1/projects/{project_id}/cover` 成功合成保存新模板；
- `POST /api/v1/projects/{project_id}/cover/upload` 比例自适应正常。

---

## 3. [R3] 分区样式编辑与 AI 分区推荐验证

### 3.1 分区覆盖渲染单测
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
d:\project\video_cut\.venv\Scripts\python.exe -m pytest tests/test_cover_generator.py -v -k "zone"
```
**期望结果**：
- `zone_styles` 覆盖 `text_color`/`stroke_color` 后渲染像素发生变化且命中覆盖色；
- `scale` 越界（如 2.0）被 clamp 到 1.4、`offset_y` 越界（如 -0.5）被 clamp 到 -0.12；
- 空 `zone_styles` 渲染结果与默认完全一致；
- 带 `zone_styles` 的配置经 `POST /cover` 保存后往返读取字段无损。

### 3.2 AI 分区推荐与 UI 手工验证
1. 触发智能剪辑分析 → 打开导出弹窗封面面板：
   - 地域区显示 AI 提炼的地名候选 chips（如"武义学车/杭州学车"），点击即套用；
   - 主标题区显示特点库与 AI 钩子候选 chips（如"2980明码标价/费用全透明"）；
   - 副标题区显示小标签候选 chips；
   - AI 未返回时三个区域仍有兜底候选（词库地名 / 特点库）。
2. 任选一个分区卡：点击色板更换文字颜色与描边颜色 → Canvas 预览毫秒级刷新且与后端保存的 `cover.jpg` 一致；
3. 拖动"大小"滑杆至两端（60%/140%）与"位置"滑杆上下移动 → 文字缩放与位移生效，且始终不越出画布与安全区视框；
4. 点击"恢复默认" → 该区样式清空回到模板默认；
5. 保存封面后重新打开面板 → 分区样式完整回显（持久化无损）。
