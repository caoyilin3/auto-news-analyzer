@echo off
chcp 65001 >nul
title AutoNewsAnalyzer Launcher
cd /d "%~dp0"

REM Prefer the project virtualenv; fall back to system python
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0start.py" %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
    echo.
    echo Launcher exited with code %CODE%
    pause
)
