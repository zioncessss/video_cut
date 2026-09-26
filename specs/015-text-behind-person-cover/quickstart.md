# Quickstart & Verification Guide: 015-text-behind-person-cover

## 1. 运行前准备 (Prerequisites)

确保项目后端服务与前端已正常启动：
```powershell
# 1. 启动后端
& d:\project\video_cut\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000

# 2. 启动前端
cd frontend; pnpm dev
```

---

## 2. 核心端到端验证场景 (E2E Verification)

### 场景 1：前端 Canvas 实时呈现“文字在人后”爆款模板
1. 打开浏览器进入剪辑工作台 `http://localhost:5173/editor`。
2. 打开“封面设计”抽屉面板。
3. 在模板选择下拉列表中，选择 `🔥 人后拱形字（3D穿插爆款）`（`text_behind_person`）。
4. **验证预期**：
   - 顶部“杭州学车”大字以优美彩虹拱形弧度展开，两端外倾，中间抬高。
   - 大字自然穿插在画面人物后方，人物头顶墨镜/发梢覆盖在大字下方边缘。
   - 人物外围有一圈靓丽的纯白贴纸发光轮廓（White Outline Glow）。
   - 底部高饱和柠檬亮黄大字（“2980全公开”）与宝蓝厚描边形成强烈视觉冲击。
   - 拖拽文案微调滑块，Canvas 60fps 实时流畅刷新，无卡顿无白屏。

### 场景 2：后端导出 1080×1920 高清封面像素级一致性验证
运行自动化集成测试：
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; & d:\project\video_cut\.venv\Scripts\python.exe -m pytest tests/test_cover_generator.py -k "test_text_behind_person"
```
**验证预期**：
- 测试绿灯通过。
- 导出的 1080×1920 封面图片中包含分层渲染，与前端 Canvas 预览严格 1:1 像素级镜像一致。

---

## 3. 实测落地与审美收敛记录 (Aesthetic Calibration Notes)

根据用户多轮视觉验收与真实爆款对标，已在工程中固化以下关键规则：
1. **背景原汁原味真实画面**：默认无背景模糊，无人工额外人物描边；
2. **去除外圈白色贴纸壳**：仅保留宝蓝主描边 + 柔和阴影，解决白框臃肿问题；
3. **消除字间漏光缝隙（Zero Gap）**：采用两阶段/形态学闭合渲染（Unified Seamless Banner），宝蓝描边彻底填实“2”与“9”之间的所有三角缝隙；
4. **三分区独立可编辑**：顶部拱形地域标、胸前引导标、底部高转化价格大词全部支持独立编辑、缩放与垂直微调。

