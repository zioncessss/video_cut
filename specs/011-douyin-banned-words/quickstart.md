# Quickstart Guide: 抖音违禁词字幕合规清洗验证指南

**Feature**: `011-douyin-banned-words`
**Date**: 2026-09-21

本指南提供端到端验证步骤，证明违禁词清洗模块能够准确识别敏感词、将其转换为用户指定的形似字、并在剪辑工作台导出弹窗中正常工作。

---

## 1. 前置条件 (Prerequisites)

- Python 3.11+ 运行环境
- 后端服务依赖已安装 (`pnpm` / `pip`)
- 违禁词库 `storage/banned_words.json` 已就绪

---

## 2. 自动化测试验证 (Automated Testing)

运行针对脱敏纯函数与贪婪匹配的单测：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
pytest tests/test_compliance_sanitizer.py -v
```

**预期结果**:
- 26 个敏感词及其衍生词（如“驾照”->“贺照”，“钱”->“銭”，“学费”->“学弗”，“体检费”->“体脸弗”）全部测试通过。
- 长词贪婪匹配（如“最快”不被“最”提前破坏）100% 验证通过。
- 高亮关键词结构体同步变换测试通过。

---

## 3. 真实视频成片验证 (End-to-End Render Verification)

对含有敏感词的真实工程执行导出测试：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
python scripts/test_compliance_render.py --project-id e4257e38-f170-45c4-84a7-ab2d2abd1547
```

**预期产物**:
1. `storage/tasks/.../subtitles.ass` 中包含：
   - `在杭州考一个贺照要多少銭`
   - `体脸弗这些加起来大概是一百`
   - `也就是咱们去考场练车的弗用`
2. 导出的视频画面中，字幕位置、字体、高亮变色正常，字符呈现对应的形似字。

---

## 4. 前端交互界面验证 (UI Verification)

1. 启动应用前后端：
   - 打开浏览器访问 `http://localhost:5173/#/editor?projectId=e4257e38-f170-45c4-84a7-ab2d2abd1547`
2. 点击工作台右上角【导出视频】按钮：
   - 观察弹出的确认 Modal；
   - 验证是否展示“开启抖音违禁词脱敏（形似字/拆字）”复选框（默认选中）；
   - 验证下方是否列出当前工程检测到的敏感词替换卡片（“驾照 -> 贺照”、“钱 -> 銭”等）；
3. 点击【确认导出】：
   - 渲染进度条正常运转；
   - 导出后自动预览成片，画面字幕显示形似字。