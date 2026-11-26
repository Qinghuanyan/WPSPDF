@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
if "%~1"=="" (
  py -3 "%~dp0open_pdf.py"
) else (
  py -3 "%~dp0open_pdf.py" "%~1"
)
endlocal
