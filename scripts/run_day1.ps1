# Run Day 1 Virtual Try-On Test
Set-Location -Path (Split-Path -Parent $PSScriptRoot)
& ".\.venv\Scripts\python.exe" "scripts\test_local.py"

