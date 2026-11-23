@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Antigravity x Gemini Catgirl Boot Animation - Installer
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ not found in PATH.
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/2] Installing runtime dependency (pywebview)...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/2] Creating Desktop shortcut...
powershell -ExecutionPolicy Bypass -File "%~dp0Install_Shortcut.ps1"
if errorlevel 1 (
    echo [ERROR] Failed to create shortcut.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Done! Double-click "Antigravity (Gemini 娘)" on Desktop
echo   or run Preview_Animation.bat to preview anytime.
echo ============================================================
pause
