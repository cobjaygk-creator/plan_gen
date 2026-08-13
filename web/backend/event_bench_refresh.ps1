$ErrorActionPreference = "Stop"
$root = "C:\Users\stkim\Documents\claude\plan_gen"
$python = Join-Path $root ".venv\Scripts\python.exe"
Set-Location (Join-Path $root "web\backend")
& $python "event_bench_refresh.py"
