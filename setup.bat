@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo       govManage - One-Click Setup Script (Windows 11)
echo ============================================================
echo.

:: ── Step 0: Change to the directory where this script lives ──────────────────
cd /d "%~dp0"

:: ────────────────────────────────────────────────────────────────────────────
:: Step 1: Check for uv (Python package manager)
:: ────────────────────────────────────────────────────────────────────────────
echo [1/5] Checking for uv (Python package manager)...
where uv >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo  uv not found. Installing uv via PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to install uv. Please install it manually:
        echo         https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    :: uv installs to %USERPROFILE%\.local\bin on Windows — add it to this session's PATH
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    :: Double-check: make sure uv is now reachable
    where uv >nul 2>&1
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] uv was installed but still cannot be found.
        echo         Please close this window, open a NEW terminal, and re-run setup.bat.
        pause
        exit /b 1
    )
    echo  uv installed successfully.
)
echo  uv is available.
echo.

:: ────────────────────────────────────────────────────────────────────────────
:: Step 2: Check for Node.js / npm (needed for the React frontend)
:: ────────────────────────────────────────────────────────────────────────────
echo [2/5] Checking for Node.js...
where node >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Node.js is not installed.
    echo         Please download and install Node.js ^(LTS^) from https://nodejs.org/
    echo         Then re-run this script.
    pause
    exit /b 1
)
node --version
echo  Node.js is available.
echo.

:: ────────────────────────────────────────────────────────────────────────────
:: Step 3: Set up Python environment and install dependencies via uv
:: ────────────────────────────────────────────────────────────────────────────
echo [3/5] Setting up Python 3.13 and installing dependencies...
uv python install 3.13
uv sync
if !ERRORLEVEL! neq 0 (
    echo [ERROR] uv setup failed. Check pyproject.toml or your connection.
    pause
    exit /b 1
)
echo  Python environment and dependencies ready.
echo.

:: ────────────────────────────────────────────────────────────────────────────
:: Step 4: Install Node.js / npm dependencies for the frontend
:: ────────────────────────────────────────────────────────────────────────────
echo [4/5] Installing frontend (React/Vite) dependencies...
cd /d "%~dp0frontend"
npm install
if !ERRORLEVEL! neq 0 (
    echo [ERROR] npm install failed inside the frontend folder.
    pause
    exit /b 1
)
cd /d "%~dp0"
echo  Frontend dependencies installed.
echo.

:: ────────────────────────────────────────────────────────────────────────────
:: Step 5: Create .env from .env.example if .env does not exist
:: ────────────────────────────────────────────────────────────────────────────
echo [5/5] Checking .env file...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo  .env created from .env.example.
        echo.
        echo  *** ACTION REQUIRED ***
        echo  Open .env and set your GROQ_API_KEY before running the project.
        echo  File location: %~dp0.env
        echo.
    ) else (
        echo [WARN] .env.example not found. Please create .env manually with:
        echo        GROQ_API_KEY=your_groq_api_key_here
        echo.
    )
) else (
    echo  .env already exists – skipping.
    echo.
)

:: ────────────────────────────────────────────────────────────────────────────
:: Done
:: ────────────────────────────────────────────────────────────────────────────
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo   Would you like to start the application now?
echo.
echo   [1] Yes - Launch everything (Backend + Agents + Frontend)
echo   [2] No  - Exit (I'll start manually later)
echo.
set /p launch_choice="Enter choice [1-2]: "

if "%launch_choice%"=="1" goto launch_all
if "%launch_choice%"=="2" goto manual_instructions
goto manual_instructions

:launch_all
echo.
echo ============================================================
echo   Launching govManage System...
echo ============================================================
echo.

:: Launch Backend API (Flask app.py)
echo [1/3] Starting Backend API (Flask)...
start "Backend-API" cmd /k "cd /d "%~dp0" && uv run python app.py"
timeout /t 2 /nobreak >nul

:: Launch All Micro-Agents
echo [2/3] Starting Micro-Agents...
start "AG-Orchestrator" cmd /k "cd /d "%~dp0" && uv run python agents_micro\orchestrator\main.py"
start "AG-PolicyAnalyst" cmd /k "cd /d "%~dp0" && uv run python agents_micro\policy_analyst\main.py"
start "AG-Compliance" cmd /k "cd /d "%~dp0" && uv run python agents_micro\compliance\main.py"
start "AG-RiskAssessment" cmd /k "cd /d "%~dp0" && uv run python agents_micro\risk_assessment\main.py"
start "AG-DecisionEngine" cmd /k "cd /d "%~dp0" && uv run python agents_micro\decision_engine\main.py"
start "AG-Audit" cmd /k "cd /d "%~dp0" && uv run python agents_micro\audit\main.py"
start "AG-Reporting" cmd /k "cd /d "%~dp0" && uv run python agents_micro\reporting\main.py"
start "AG-Feedback" cmd /k "cd /d "%~dp0" && uv run python agents_micro\feedback\main.py"
start "AG-Persistence" cmd /k "cd /d "%~dp0" && uv run python agents_micro\persistence\main.py"
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
echo   Close this window when done.
echo ============================================================
echo.
pause
exit /b 0

:manual_instructions
echo.
echo ============================================================
echo   Manual Launch Instructions
echo ============================================================
echo.
echo   To start the project later, run:
echo.
echo   1. Backend API:
echo      uv run python app.py
echo.
echo   2. All Micro-Agents (use launch_agents.bat):
echo      launch_agents.bat
echo.
echo   3. Frontend:
echo      cd frontend ^&^& npm run dev
echo.
echo   Or simply run setup.bat again and choose option [1]
echo ============================================================
echo.
pause
