@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================
echo  WPSPDF 一键卸载
echo ============================================
echo.
echo [1/4] 移除 PDF 右键菜单
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-pdf-menu.ps1" -Action unregister
echo.
echo [2/4] 移除离线本地包加载项
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-offline.ps1" -Action unregister
echo.
echo [3/4] 移除按需启动计划任务（若曾安装）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-watchdog-task.ps1" -Action unregister
echo.
echo [4/4] 移除轻量加载器自启（若曾安装）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-loader.ps1" -Action unregister
echo.
echo 完成。停掉仍在跑的引擎：tools\stop-engine.bat
echo.
pause
endlocal
