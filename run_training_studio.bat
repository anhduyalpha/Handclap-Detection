@echo off
chcp 65001 >nul
title HandClap AI - Training Studio Pro (Windows)

echo ==================================================================
echo   🔥 HANDCLAP AI - TRAINING STUDIO PRO (WINDOWS LAUNCHER)
echo ==================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_training_studio.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_training_studio.py
) else (
    python run_training_studio.py
)

pause
