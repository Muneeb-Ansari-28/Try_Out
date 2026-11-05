@echo off
echo ============================================================
echo   🧥 Live Virtual Try-On - Day 1 Interactive Test
echo   Controls:
echo     [N]   - Next garment
echo     [1-4] - Select garment directly
echo     [C]   - Clear garment
echo     [Q]   - Quit
echo ============================================================
cd /d %~dp0\..
.\.venv\Scripts\python.exe scripts\test_local.py
pause

