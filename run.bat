@echo off
REM Starts the Hospital Module using the project's virtual environment.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run setup.bat first.
  pause
  exit /b 1
)
cd backend
echo Open http://127.0.0.1:8000  (API docs: http://127.0.0.1:8000/docs)
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
pause
