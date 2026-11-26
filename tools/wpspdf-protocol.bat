@echo off
rem WPSPDF 自定义协议处理器：被 wpspdf://start 唤起时执行
rem 先写一个命中标记（便于验证协议链路是否真的被触发），再静默起引擎
chcp 65001 >nul
setlocal
set ROOT=D:\Github\WPSPDF
echo %DATE% %TIME% protocol-hit > "%ROOT%\.run\protocol-hit.txt"
start "" /min wscript.exe "%ROOT%\tools\engine-silent.vbs"
endlocal
