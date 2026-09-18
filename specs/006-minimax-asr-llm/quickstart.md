# Quickstart & Verification Guide: MiniMax 统一接管 ASR 与智能剪辑 (006-minimax-asr-llm)

本指南包含可独立执行、端到端验证 MiniMax ASR 极速语音识别与大模型智能剪辑特性的测试步骤。

---

## 1. 自动化单元与集成测试 (Automated Tests)

### 场景 1: MiniMax 语音识别适配器与逐字时间戳转换验证
- **测试命令**:
  ```bash
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_minimax_asr.py -v
  ```
- **验证断言**:
  - MiniMax 返回的 `segments` 成功转换为 `words: [{word, start, end}]`；
  - 接入 `split_into_readable_segments` 后生成的字幕句严格保持在 6~12 字区间；
  - 各字幕句起止时间精准继承首字 `start` 与尾字 `end`，无时间戳丢失。

### 场景 2: 网络异常/未配 Key 自动降级本地 Whisper 测试
- **测试命令**:
  ```bash
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_minimax_asr.py -k "test_degradation_to_local_whisper" -v
  ```
- **验证断言**:
  - 当 MiniMax 返回 HTTP 401/500 或连接超时，系统自动捕获并无缝回退至 `faster-whisper`；
  - 转写流程不抛出未捕获崩溃，返回正常字幕段落。

### 场景 3: 全自动剪辑链路全景回归 (端到端)
- **测试命令**:
  ```bash
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .venv\Scripts\python.exe -m pytest tests/test_all_flows.py -v
  ```
- **验证断言**:
  - 全流程（音轨抽取 $\to$ ASR 转写 $\to$ MiniMax-Text-01 字幕纠偏 $\to$ MiniMax-Text-01 分镜决策 $\to$ FFmpeg 渲染）顺畅走通，全部 3 项端到端单测绿色通过。

---

## 2. 手工界面走查验证 (Manual GUI Walkthrough)

### 场景 4: 设置中心配置与一键连通性测试
1. 启动桌面应用或执行 `python launcher.py` 打开前台；
2. 点击左侧导航进入「设置」页面；
3. 检查接入提供商选择「MiniMax」，填入有效 API Key，模型选择 `MiniMax-Text-01`，开启「云端极速 ASR」；
4. 点击「保存设置」，刷新页面，验证界面只显示实心绿点与已配置标签（Key 输入框为掩码或已隐藏明文）；
5. 点击「测试连通性」按钮，等待 1~2 秒，观察弹出「MiniMax 大模型与语音识别双通道就绪」成功提示。

### 场景 5: 剪辑工作台实测极速转写体验
1. 进入「剪辑工作台」，点击顶部「+ 上传口播视频」上传一段 60 秒口播视频；
2. 观察进度条：ASR 阶段在 3~5 秒内迅速完成（以往本地 CPU 需 40 秒以上）；
3. 观察时间轴生成的字幕短句，确认每句 6~12 字、无中文词语腰斩断裂；
4. 确认画面与字幕高亮时间对齐精确。