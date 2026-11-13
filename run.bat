@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo               Starting CopyCop System
echo ===================================================

REM Check for virtual environment Python or system Python
if exist ".venv\Scripts\python.exe" (
    set "PY_BIN=.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python was not found in PATH or in .venv.
        pause
        exit /b 1
    )
    set "PY_BIN=python"
)

REM Execute the unified runner
"%PY_BIN%" run.py %*

if %errorlevel% neq 0 (
    echo.
    echo CopyCop runner exited with code %errorlevel%.
    pause
)
