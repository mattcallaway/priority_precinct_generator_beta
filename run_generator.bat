@echo off
echo ========================================================
echo        Priority Precinct Generator - Startup
echo ========================================================
echo.
echo Preparing the Python Virtual Environment...

if not exist venv (
    echo [1/3] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/3] Virtual environment found.
)

echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/3] Checking and installing requirements (this may take a minute on first run)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

echo.
echo ========================================================
echo     Starting the web application dashboard...
echo     Please wait, opening in your default browser...
echo ========================================================
streamlit run app.py
pause
