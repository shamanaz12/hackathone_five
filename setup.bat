@echo off
REM ============================================================
REM TaskFlow AI Support Agent — Quick Start (Windows)
REM CRM Digital FTE Factory Final Hackathon 5
REM ============================================================

echo.
echo ========================================
echo TaskFlow AI Support Agent — Setup
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Running test suite (mock mode)...
python test_runner.py
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some tests failed, but you can still start the server.
    echo.
)

echo.
echo [3/3] Setup complete!
echo.
echo To start the FastAPI server, run:
echo     uvicorn production.api.main:app --reload --port 8000
echo.
echo Then open: http://localhost:8000/api/docs
echo.
pause
