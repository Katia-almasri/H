@echo off
echo ========================================
echo Harvest FastAPI Project Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment...
if not exist .venv (
    python -m venv .venv
    echo Virtual environment created successfully
) else (
    echo Virtual environment already exists
)
echo.

echo [2/5] Activating virtual environment...
call .venv\Scripts\activate.bat
echo.

echo [3/5] Upgrading pip...
python -m pip install --upgrade pip
echo.

echo [4/5] Installing dependencies...
pip install -r requirements.txt
echo.

echo [5/5] Setting up environment file...
if not exist .env (
    copy .env.example .env
    echo .env file created from .env.example
    echo Please update .env with your configuration
) else (
    echo .env file already exists
)
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Update .env file with your configuration
echo 2. Start Docker services: docker-compose up -d
echo 3. Run the application: uvicorn app.main:app --reload
echo.
echo To activate the virtual environment in future sessions:
echo   .venv\Scripts\activate
echo.
pause
