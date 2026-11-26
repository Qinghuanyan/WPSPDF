@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================
echo  WPSPDF 一键卸载
echo ============================================
echo.
echo [1/4] 移除按需启动计划任务
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-watchdog-task.ps1" -Action unregister
echo.
echo [2/4] 移除 PDF 右键菜单
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-pdf-menu.ps1" -Action unregister
echo.
echo [3/4] 移除离线本地包加载项
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-offline.ps1" -Action unregister
echo.
echo [4/4] 清理在线加载项登记（若曾安装）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\uninstall.ps1"
echo.
echo 完成。引擎是普通进程，已随 WPS 关闭自动退出；若仍在跑可执行 tools\stop-engine.bat。
echo.
pause
endlocal
