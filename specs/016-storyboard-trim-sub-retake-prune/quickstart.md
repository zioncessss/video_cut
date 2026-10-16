# Quickstart & Verification Guide: 自主分镜切入裁剪与字幕重叠定位原口播视频误读裁剪 (Storyboard Trim & Subtitle Retake Pruning)

**Feature Branch**: `016-storyboard-trim-sub-retake-prune`
**Date**: 2026-10-14

## Verification Prerequisites

- Python 虚拟环境可用：`.\.venv\Scripts\pytest.exe`
- 环境变量防乱码：`$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'`
- 前端开发环境：Node.js 18+, Vite

---

## Scenario 1: ASR 阶段短句重读阻断测试
- **目标**：验证当创作者在 0.55s 内短暂停顿并重读时，`merge_short_segments` 不会将口误与正句粘连。
- **验证命令**：
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_asr_retake_guard.py -v
  ```
- **预期结果**：前缀相同（如“顺达...”与“顺达驾校”）的两个短片段保持独立，成功输出 2 个 segment。

---

## Scenario 2: 口误读错重录识别与前缀重叠算法
- **目标**：验证 `find_repeated_takes` 面对短前缀口误（如 4 字 vs 20 字）能稳定识别，且排比连读（gap < 0.2s）不被误判。
- **验证命令**：
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_prune_retake_prefix.py -v
  ```
- **预期结果**：口误被精准识别并标记，置信度 $\ge 0.90$；排比句与独立长句被安全网拦截未被标记。

---

## Scenario 3: 原视频音画物理裁剪端到端验证
- **目标**：验证剔除误读后，底层 FFmpeg 真实切除了原口播视频的音画，导出的视频时长准确减少，且无爆音。
- **验证命令**：
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_prune_video_export.py -v
  ```
- **预期结果**：所有断言通过，导出文件时长等于原始时长减去裁剪时长，未发生静默跳过或假替换。

---

## Scenario 4: 分镜素材源起始点 (source_start_time) 截取与覆盖
- **目标**：验证分镜素材从指定 In 点截取并静音覆盖口播视频画面。
- **验证命令**：
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_broll_source_trim.py -v
  ```
- **预期结果**：滤镜字符串包含 `trim=start={source_start_time}`，且最终视频在指定切入区间展现分镜画面。

---

## Scenario 5: 前端实时预览与卡片就地收纳 (E2E / Component Test)
- **目标**：验证前端在播放器中执行虚拟跳播与分镜贴片覆盖，被删卡片在字幕列表中折叠为浅灰条并可一键恢复。
- **验证方式**：在浏览器或测试套件中打开工作台，点击卡片剔除，播放器自动跳播，点击浅灰条上的“恢复”，时间轴瞬间复原。
