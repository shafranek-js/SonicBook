@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ARGS="
if /I "%SONICBOOK_OPEN_BROWSER%"=="0" set "ARGS=-NoBrowser"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_sonicbook.ps1" %ARGS%
exit /b %ERRORLEVEL%
