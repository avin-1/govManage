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
echo   To start the project, run each of these in a separate terminal:
echo.
echo   1. Backend API:
echo      uv run uvicorn api:app --reload --port 8000
echo.
echo   2. Agent microservices (one terminal each):
echo      uv run agents_micro\compliance\main.py
echo      uv run agents_micro\policy_analyst\main.py
echo      uv run agents_micro\risk_assessment\main.py
echo      uv run agents_micro\decision_engine\main.py
echo      uv run agents_micro\orchestrator\main.py
echo.
echo   3. Frontend (React/Vite):
echo      cd frontend ^&^& npm run dev
echo.
echo ============================================================
echo.
pause
