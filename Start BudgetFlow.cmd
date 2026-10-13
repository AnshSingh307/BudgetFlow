@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo BudgetFlow's Python environment is missing.
    echo Follow the installation instructions in README.md first.
    pause
    exit /b 1
)

echo Starting BudgetFlow at http://localhost:8501
echo Keep this window open while using the app. Press Ctrl+C to stop it.
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.headless false

if errorlevel 1 (
    echo.
    echo BudgetFlow could not start. Review the message above.
    echo If port 8501 is already in use, check whether the app is already running.
    pause
)
