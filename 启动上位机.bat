@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "%~dp0dist\LX04-PC-Bridge-Host.exe" (
  start "" "%~dp0dist\LX04-PC-Bridge-Host.exe"
  exit /b 0
)

for /f "delims=" %%F in ('dir /b /o:-n "%~dp0dist\LX04-PC-Bridge-Host-v*.exe" 2^>nul') do (
  start "" "%~dp0dist\%%F"
  exit /b 0
)

echo 还没有上位机 exe。请先运行: python build_host_exe.py
pause
