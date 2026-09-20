# Quickstart & Verification: 008-speed-clean-ui-batch

## 1. 自动化单元测试
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; uv run pytest tests/test_subtitle_strategy.py tests/test_editor_api.py tests/test_batch_api.py
```
- 验证 `EditingStrategy.video_speed` 参数序列化与边界校验
- 验证带有 `video_speed` 的合成滤镜正确装配 `atempo` 与 `setpts`
- 验证字幕起止时间与空镜时间除以 `speed` 等比缩放

## 2. 前端构建测试
```powershell
$env:NO_UPDATE_NOTIFIER='1'; $env:CI='1'; pnpm build; exit $LASTEXITCODE
```
- 验证 TypeScript 静态类型与 Vite 打包 0 错误。

## 3. 人工视觉与体验核验
1. **工作台极简去繁核验**:
   - 打开 `/editor`，核验原蓝色模式长横条已收缩为现代 Segmented Switch `[ 实时编辑 | 成片预览 ]`；
   - 核验各按钮标签精炼单行（`智能初剪`、`导出成片`、`上传封面`）；
   - 打开策略面板，核验语速档位（1.0x / 1.1x / 1.2x）切换流畅，无冗长说明段落。
2. **视频加速成片核验**:
   - 选择 1.15x 或 1.2x 倍速，点击导出成片；
   - 播放成片核验音调自然（无变调）、真人发音加速干脆，字幕折行与关键词高光与语音严格对齐。
3. **批量混剪驾驶舱核验**:
   - 打开 `/batch`，默认展现成片画廊，卡片清晰展示封面、标题与时长；
   - 切换至队列模式，查看任务流水线执行；
   - 顶部控制台设置 1.1x 倍速并添加多个口播素材，批量任务稳定执行。