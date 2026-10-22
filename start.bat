@echo off
chcp 65001 >nul
title MijiaDeck
cd /d "%~dp0"

:: 1. Detect Python: try py launcher, fall back to python
set "PYTHON=python"
where py >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"

if not exist ".venv\Scripts\python.exe" (
    echo [INIT] Creating virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :fail
    echo [INIT] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --quiet -e .
    if errorlevel 1 goto :fail
    echo [INIT] Done.
)

echo [START] MijiaDeck
".venv\Scripts\python.exe" -X utf8 run.py
if errorlevel 1 (
    echo.
    echo [ERROR] Program exited with error. Screenshot the above info for debugging.
    pause
    exit /b 1
)
exit /b 0

:fail
echo [ERROR] Failed to initialize. Make sure Python 3 is installed and on PATH.
pause
exit /b 1
