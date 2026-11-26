@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================
echo  WPSPDF 一键安装
echo ============================================
echo.
echo [1/3] 安装 PDF 侧「离线本地包」加载项（页签不依赖引擎常驻）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-offline.ps1" -Action register
echo.
echo [2/3] 注册「按需启动」计划任务（仅当 WPS 在跑才拉起引擎）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-watchdog-task.ps1" -Action register
echo.
echo [3/3] 注册 PDF 右键菜单「PDF 转表格（WPSPDF）」
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-pdf-menu.ps1" -Action register
echo.
echo 完成。生效方式：完全退出 WPS，然后打开任意 PDF。
echo   页签「PDF转表格」直接出现（本地包，不需要引擎先跑）；
echo   引擎由计划任务在 WPS 运行时按需拉起，WPS 关闭后约 20 秒自动退出。
echo.
pause
endlocal
