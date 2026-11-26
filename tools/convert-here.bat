@echo off
chcp 65001 >nul
rem 把 PDF 拖到本文件上即可转换（不需要 WPS 打开）
cd /d "%~dp0.."
if "%~1"=="" (
  echo 用法：把 PDF 文件拖到本 bat 上
  pause
  exit /b 1
)
echo 正在转换: %~nx1
py -3 engine\convert.py "%~1" -o "output\%~n1.xlsx"
echo.
echo 产物目录: %cd%\output
pause
