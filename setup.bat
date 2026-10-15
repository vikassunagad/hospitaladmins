@echo off
REM One-time setup: creates .venv, installs packages, creates .env, seeds database.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if not exist ".env" copy ".env.example" ".env"
cd backend
"..\.venv\Scripts\python.exe" seed.py
echo.
echo Setup complete. Now double-click run.bat
pause
