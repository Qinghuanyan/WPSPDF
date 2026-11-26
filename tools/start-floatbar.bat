@echo off
chcp 65001 >nul
cd /d "%~dp0.."
start "" pyw -3 engine\floatbar.py
