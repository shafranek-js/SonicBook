@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ARGS=-Background"
if /I "%SONICBOOK_OPEN_BROWSER%"=="0" set "ARGS=-Background -NoBrowser"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_sonicbook.ps1" %ARGS%
exit /b %ERRORLEVEL%
