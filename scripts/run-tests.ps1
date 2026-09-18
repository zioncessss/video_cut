# Run pytest with UTF-8 encoding and proper environment settings
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $PythonExe)) { $PythonExe = 'python' }

if ($args.Count -eq 0) {
    & $PythonExe -m pytest tests/ -v
} else {
    & $PythonExe -m pytest @args
}
exit $LASTEXITCODE
