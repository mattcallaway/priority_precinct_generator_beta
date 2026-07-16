#!/bin/bash
echo "========================================================"
echo "       Priority Precinct Generator - Startup (macOS/Linux)"
echo "========================================================"
echo ""
echo "Checking and setting up the Python environment..."

if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment (venv)..."
    python3 -m venv venv
else
    echo "[1/3] Virtual environment found."
fi

echo "[2/3] Activating virtual environment..."
source venv/bin/activate

echo "[3/3] Installing requirements (this may take a minute on first run)..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

echo ""
echo "========================================================"
echo "    Starting the web application dashboard..."
echo "    Opening in your browser..."
echo "========================================================"
streamlit run app.py
