@echo off
setlocal EnableExtensions

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($conn) { $conn.OwningProcess }"`) do set "SONICBOOK_PID=%%P"

if not defined SONICBOOK_PID (
    echo SonicBook is not running on port 8000.
    exit /b 0
)

echo Stopping SonicBook process %SONICBOOK_PID%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-Process -Id %SONICBOOK_PID% -Force"

if errorlevel 1 (
    echo Failed to stop process %SONICBOOK_PID%.
    exit /b 1
)

echo SonicBook stopped.
exit /b 0
