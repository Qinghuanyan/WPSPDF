@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
echo [WPSPDF] 启动本地引擎（关闭此窗口即停止）...
py -3 engine\server.py 38731
if errorlevel 1 python engine\server.py 38731
endlocal
