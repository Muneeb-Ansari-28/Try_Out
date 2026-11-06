@echo off
:: start.bat [FIX H11]
title Virtual Try-On Studio Launcher
echo ========================================================
echo   Launching Virtual Try-On App (T550 4GB Local Stack)
echo ========================================================
cd /d %~dp0

:: Check if local repo .venv exists first
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Detected .venv virtual environment.
    set ACTIVATE_CMD=call .venv\Scripts\activate.bat
) else (
    :: Locate conda.bat safely
    set CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat
    if not exist "%CONDA_BAT%" set CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat
    if not exist "%CONDA_BAT%" set CONDA_BAT=%LOCALAPPDATA%\miniconda3\condabin\conda.bat

    if not exist "%CONDA_BAT%" (
        echo [ERROR] Neither .venv nor conda.bat found.
        pause
        exit /b 1
    )
    set ACTIVATE_CMD=call "%CONDA_BAT%" activate vton
)

:: 1. Launch FastAPI Backend
echo [1/3] Starting Backend Server on http://127.0.0.1:8000 ...
start "VTON Backend" cmd /k "%ACTIVATE_CMD% && uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: Wait for backend to bind port
timeout /t 3 /nobreak > nul

:: 2. Launch Next.js Frontend
echo [2/3] Starting Next.js 15 Frontend on http://localhost:3000 ...
start "VTON Frontend" cmd /k "cd frontend && npm run dev"

:: Wait for Next.js dev server
timeout /t 5 /nobreak > nul

:: 3. Launch Web Browser
echo [3/3] Opening Browser...
start http://localhost:3000

echo.
echo Virtual Try-On is running! Close the terminal windows to stop.

