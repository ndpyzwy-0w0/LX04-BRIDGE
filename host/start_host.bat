@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python pc_host.py
) else (
    py -3 pc_host.py
)
if errorlevel 1 pause
