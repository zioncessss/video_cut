# Quickstart Validation: 017-recompose-speed-and-orphan-prune-fix

## 验证步骤与命令

### 1. 粗剪防跳剪单元测试
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\pytest.exe tests/test_auto_prune_engine.py -v -k "ghost or orphan or bridge or head"
```
**预期**:
- 连续删除两个字幕（如 0.8~2.24 与 2.76~3.54）时，中间 0.52s 间隙被自动连片剪切，保留区间数量为 1，无任何幽灵碎片。

### 2. 重新合成单次直出测试
```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\pytest.exe tests/test_render_fast_path.py -v
```
**预期**:
- 底包未命中时，单次调用即产出带 ASS 字幕的成片，耗时降低 50% 以上。

### 3. 当前工程现场数据自愈验证
```powershell
$env:PYTHONPATH='backend'; .\.venv\Scripts\python.exe -c "
import sqlite3, json
from app.native_engine.prune_engine import auto_prune_engine
# 校验湖州驾校工程经新算法计算后保留区间
"
```
**预期**:
- 湖州驾校工程开篇第一条字幕紧凑时间戳恢复为 `00:00.00`，0.52 秒幽灵碎片彻底消除。
