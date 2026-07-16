@echo off
echo ========================================================
echo        Priority Precinct Generator - Startup (Windows)
echo ========================================================
echo.
echo Checking and setting up the Python environment...

if not exist venv (
    echo [1/3] Creating virtual environment (venv)...
    python -m venv venv
) else (
    echo [1/3] Virtual environment found.
)

echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/3] Installing requirements (this may take a minute on first run)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

echo.
echo ========================================================
echo     Starting the web application dashboard...
echo     Opening in your browser...
echo ========================================================
streamlit run app.py
pause
