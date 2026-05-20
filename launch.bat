@echo off
echo ============================================================
echo       govManage - Quick Launch
echo ============================================================
echo.
echo Starting all services...
echo.

:: Change to script directory
cd /d "%~dp0"

:: Launch Backend API (Flask app.py)
echo [1/3] Starting Backend API (Flask)...
start "Backend-API" cmd /k "uv run python app.py"
timeout /t 2 /nobreak >nul

:: Launch All Micro-Agents
echo [2/3] Starting Micro-Agents...
start "AG-Orchestrator" cmd /k "uv run python agents_micro\orchestrator\main.py"
start "AG-PolicyAnalyst" cmd /k "uv run python agents_micro\policy_analyst\main.py"
start "AG-Compliance" cmd /k "uv run python agents_micro\compliance\main.py"
start "AG-RiskAssessment" cmd /k "uv run python agents_micro\risk_assessment\main.py"
start "AG-DecisionEngine" cmd /k "uv run python agents_micro\decision_engine\main.py"
start "AG-Audit" cmd /k "uv run python agents_micro\audit\main.py"
start "AG-Reporting" cmd /k "uv run python agents_micro\reporting\main.py"
start "AG-Feedback" cmd /k "uv run python agents_micro\feedback\main.py"
start "AG-Persistence" cmd /k "uv run python agents_micro\persistence\main.py"
timeout /t 3 /nobreak >nul

:: Launch Frontend (React/Vite)
echo [3/3] Starting Frontend (React/Vite)...
start "Frontend-Vite" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================================
echo   All Services Launched!
echo ============================================================
echo.
echo   Backend API:  http://localhost:5000
echo   Frontend:     http://localhost:5173
echo.
echo   Keep all terminal windows open for the system to work!
echo   Close individual windows to stop services.
echo ============================================================
echo.
pause
