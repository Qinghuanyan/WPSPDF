@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================
echo  WPSPDF 一键安装（零常驻方案）
echo ============================================
echo.
echo [1/2] 安装 PDF 侧「离线本地包」加载项（页签不依赖任何服务）
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install-offline.ps1" -Action register
echo.
echo [2/2] 注册 PDF 右键菜单「PDF 转表格（WPSPDF）」
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\register-pdf-menu.ps1" -Action register
echo.
echo 完成。用法：完全退出 WPS 后，右键任意 PDF 文件
echo   →「PDF 转表格（WPSPDF）」→ 自动起引擎并用 WPS 打开，转换完引擎自行退出。
echo.
echo 说明：本方案零常驻，没有任何后台进程/计划任务。
echo   若想要「WPS 窗格里一键启动引擎」，再运行：
echo     pwsh -File tools\install-loader.ps1 -Action register   （常驻 27MB 的小加载器）
echo.
pause
endlocal
