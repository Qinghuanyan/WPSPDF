@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
echo [WPSPDF] 检查本地引擎…
py -3 "%~dp0check_engine.py"
if errorlevel 1 echo   提示：引擎没在跑。双击 tools\start-engine.bat 或 tools\engine-silent.vbs 启动。
echo.
pause
endlocal
