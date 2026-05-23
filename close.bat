@echo off
echo ============================================================
echo       govManage - Shutdown All Services
echo ============================================================
echo.
echo Stopping all running services...
echo.

:: 1. Kill by window title (matches titles set in launch.bat)
echo [1/4] Closing terminal windows by title...
taskkill /FI "WINDOWTITLE eq Backend-API*"    /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Orchestrator*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-PolicyAnalyst*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Compliance*"   /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-RiskAssessment*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-DecisionEngine*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Audit*"        /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Reporting*"    /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Feedback*"     /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Persistence*"  /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend-Vite*"   /F >nul 2>&1

:: 2. Kill processes by command-line content using PowerShell (replaces deprecated wmic)
echo [2/4] Terminating backend Python/uv processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*app.py*' -and ($_.Name -eq 'python.exe' -or $_.Name -eq 'uv.exe') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*agents_micro*' -and ($_.Name -eq 'python.exe' -or $_.Name -eq 'uv.exe') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [3/4] Terminating frontend Node/npm processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*vite*' -and $_.Name -eq 'node.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*npm*run*dev*' -and $_.Name -eq 'node.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

:: 3. Kill anything still holding ports 5000 (Flask) and 5173 (Vite)
echo [4/4] Releasing ports 5000 and 5173...
powershell -NoProfile -Command "try { $p = (Get-NetTCPConnection -LocalPort 5000 -ErrorAction Stop).OwningProcess | Select-Object -Unique; $p | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } catch {}"
powershell -NoProfile -Command "try { $p = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction Stop).OwningProcess | Select-Object -Unique; $p | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } catch {}"

echo.
echo ============================================================
echo   All Services Stopped!
echo ============================================================
echo.
echo   You can now safely close this window.
echo ============================================================
echo.
pause
