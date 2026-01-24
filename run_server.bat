@echo off
echo Check for Python...
python --version
if errorlevel 1 (
    echo Python not found. Please install Python 3.9+
    pause
    exit /b
)

if not exist ".temp_env" (
    echo Creating virtual environment...
    python -m venv .temp_env
)

echo Installing dependencies...
.\.temp_env\Scripts\pip install -r requirements.txt

echo Starting CampusIQ Backend...
.\.temp_env\Scripts\uvicorn backend.app:app --host 0.0.0.0 --port 8000 --env-file .env
pause
