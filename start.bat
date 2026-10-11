@echo off
chcp 65001 >nul
cls

echo ╔══════════════════════════════════════════════════════════╗
echo ║                AutoNewsAnalyzer v2.0                    ║
echo ║        Self-Evolving AI-Powered News Analysis System     ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:menu
echo Available Operations:
echo.
echo [1] 🛠️  Initial Project Setup
echo [2] 🚀 Run in Development Mode
echo [3] 🏭 Run in Production Mode
echo [4] 🧪 Run Tests
echo [5] 🌐 Start API Server
echo [6] 💻 Command Line Interface
echo [7] 🔍 Check Environment
echo [8] ❌ Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" goto setup
if "%choice%"=="2" goto dev
if "%choice%"=="3" goto prod
if "%choice%"=="4" goto test
if "%choice%"=="5" goto api
if "%choice%"=="6" goto cli
if "%choice%"=="7" goto check
if "%choice%"=="8" goto exit

echo ❌ Invalid selection, please try again
timeout /t 2 >nul
goto menu

:setup
python start.py setup
pause
goto menu

:dev
python start.py dev
pause
goto menu

:prod
python start.py prod
pause
goto menu

:test
python start.py test
pause
goto menu

:api
python start.py api
pause
goto menu

:cli
python start.py cli
pause
goto menu

:check
python start.py check
pause
goto menu

:exit
echo.
echo 👋 Goodbye!
timeout /t 2 >nul
exit