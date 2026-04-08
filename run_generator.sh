#!/bin/bash
echo "========================================================"
echo "       Priority Precinct Generator - Startup"
echo "========================================================"
echo ""
echo "Preparing the Python Virtual Environment..."

if [ ! -d "venv" ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv venv
else
    echo "[1/3] Virtual environment found."
fi

echo "[2/3] Activating virtual environment..."
source venv/bin/activate

echo "[3/3] Checking and installing requirements..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

echo ""
echo "========================================================"
echo "    Starting the web application dashboard..."
echo "    Please wait, opening in your default browser..."
echo "========================================================"
streamlit run app.py
