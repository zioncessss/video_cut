# Quickstart & Verification: 剪辑策略与字幕效果验证 (003-subtitle-strategy-preview)

## 1. 验证目标
验证口播视频剪辑中：
1. ASR 句子不过长，切分符合 6~12 字移动端黄金视读体验。
2. 在工作台「剪辑策略组合面板」切换字幕主题、高亮模式、顶部 Title、品牌水印，播放器实时预览生效。
3. 点击“生成预览”，FFmpeg 完整复刻输出包含顶部标题、黄色高亮字和水印的成片。

---

## 2. 自动化测试执行

```powershell
$env:PYTHONPATH='backend'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m pytest tests/test_subtitle_strategy.py
```

---

## 3. 手工 UI 流程体验

1. 打开浏览器访问 `http://127.0.0.1:18888/#/editor`。
2. 选择一个口播视频，点击 **「AI 智能识别与初剪」**。
3. 在右侧面板切换到 **「策略实验 (Strategy Studio)」** 选项卡：
   - 切换字幕主题为 **「爆款金黄」**，观察播放器中的文字变为粗黑边底框加金黄高亮。
   - 勾选 **「开启顶部大标题」**，输入 `🔥 科目二必过秘籍`，观察播放器顶部浮现精致横幅。
   - 勾选 **「开启品牌水印」**，输入 `@东方驾校官方`，观察播放器右上角浮现微透明角标。
4. 点击 **「生成预览 (Generate Preview)」**，等待压制完成后，点击播放器播放导出的 MP4，确认烧录效果与预览完全吻合。