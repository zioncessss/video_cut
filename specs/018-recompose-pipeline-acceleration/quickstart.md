# Quickstart: 重新合成全链路深度提速与管线优化

## 运行回归测试

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $OutputEncoding = [System.Text.UTF8Encoding]::new(); $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_render_fast_path.py -v
```

## 运行性能与管线加速专项测试

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $OutputEncoding = [System.Text.UTF8Encoding]::new(); $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\pytest.exe tests/test_recompose_acceleration.py -v
```
