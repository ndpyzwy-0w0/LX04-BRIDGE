@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "%~dp0dist\LX04-PC-Bridge-Host\LX04-PC-Bridge-Host.exe" (
  start "" "%~dp0dist\LX04-PC-Bridge-Host\LX04-PC-Bridge-Host.exe"
  exit /b 0
)
if exist "%~dp0dist\LX04-PC-Bridge-Host.exe" (
  start "" "%~dp0dist\LX04-PC-Bridge-Host.exe"
  exit /b 0
)

echo 还没有上位机。请先运行: python build_host_exe.py
pause
