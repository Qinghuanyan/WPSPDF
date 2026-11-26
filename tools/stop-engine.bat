@echo off
chcp 65001 >nul
echo 正在停止 WPSPDF 引擎...
curl -s -m 3 http://127.0.0.1:38731/shutdown >nul 2>&1
timeout /t 2 >nul
tasklist | findstr /i "pythonw" >nul && echo 引擎已停止（若仍有进程，请用任务管理器结束 pythonw）
exit /b 0
