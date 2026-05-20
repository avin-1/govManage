@echo off
echo ============================================================
echo       govManage - Shutdown All Services
echo ============================================================
echo.
echo Stopping all running services...
echo.

:: Kill Backend API
echo [1/3] Stopping Backend API...
taskkill /FI "WINDOWTITLE eq Backend-API*" /F >nul 2>&1

:: Kill All Micro-Agents
echo [2/3] Stopping Micro-Agents...
taskkill /FI "WINDOWTITLE eq AG-Orchestrator*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-PolicyAnalyst*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Compliance*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-RiskAssessment*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-DecisionEngine*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Audit*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Reporting*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Feedback*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AG-Persistence*" /F >nul 2>&1

:: Kill Frontend
echo [3/3] Stopping Frontend...
taskkill /FI "WINDOWTITLE eq Frontend-Vite*" /F >nul 2>&1

:: Also kill any remaining Python/Node processes from these services
echo.
echo Cleaning up remaining processes...
taskkill /IM python.exe /FI "WINDOWTITLE eq Backend-API*" /F >nul 2>&1
taskkill /IM python.exe /FI "WINDOWTITLE eq AG-*" /F >nul 2>&1
taskkill /IM node.exe /FI "WINDOWTITLE eq Frontend-Vite*" /F >nul 2>&1

echo.
echo ============================================================
echo   All Services Stopped!
echo ============================================================
echo.
echo   All terminal windows have been closed.
echo   You can now safely close this window.
echo ============================================================
echo.
pause
