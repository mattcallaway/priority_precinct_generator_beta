# 🗺️ Priority Precinct Generator (Realigned Version)

The **Priority Precinct Generator (PPG)** is a Voter-File-First canvassing and campaign targeting engine. It aggregates raw individual-level voter registration database files directly by `PrecinctName` as the primary scoring unit, integrates optional geographic hierarchy shapefiles, and applies strict election contest performance scores to produce priority precinct lists for strategic resource allocation.

---

## 🚀 Core Architecture Goals

PPG operates under four core principles:

1. **Voter-File-First:** Precinct aggregation and demographics are computed directly from individual voter rows in `voter_file.csv`.
2. **Strict Contest Enrichment:** Real-world election contest performance data (from Statement of Votes files) is required to compile production rankings.
3. **Optional Geography:** Legislative districts and city boundaries can be derived from shapefile spatial overlays, external crosswalks, or Sonoma prefix rules. When shapefiles are missing, the engine automatically falls back to the **Operational Scale Proxy** ($\ln(1 + \text{Total\_Voters})$) instead of True Density.
4. **Data Verification:** Built-in checks enforce strict logic validation (e.g., verifying turnout rates, crosswalk coverage, and warning of data mismatch issues).

---

## 📂 Project Directory Structure

```text
PPG/
├── app.py                     # Streamlit frontend dashboard
├── main.py                    # Core targeting math engine
├── contest_manager.py         # SOV file classification and enrichment math
├── file_manager.py            # Central data repository and metadata tracker
├── geo_processor.py           # GIS overlay engine (Shapefiles & Area extraction)
├── core_diagnostics.py        # Diagnostic reports and pipeline validations
├── run_audit_tests.py         # Mathematical engine testing suite
├── docs/                      # Documentation folder
│   ├── README.md              # Project Overview
│   ├── walkthrough.md         # Step-by-Step User Guide
│   ├── technical_map.md       # Full Developer Technical Map
│   └── theory_explainer.md    # Math and Formula Specification
├── data/                      # Active working directory for data inputs
└── outputs/                   # Standardized targeting outputs and reports
```

---

## ⚙️ Quick Start Guide

You can install and run the application automatically using the provided cross-platform startup scripts, or do it manually.

### ⚡ Option A: 1-Click Auto Run (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/PPG.git
   cd PPG
   ```

2. **Execute the script for your platform:**
   * **Windows:** Double-click on `run.bat` (or run `run.bat` in Command Prompt/PowerShell).
   * **macOS / Linux:** Open the Terminal, navigate to the folder, and run:
     ```bash
     chmod +x run.sh
     ./run.sh
     ```

The script will automatically detect Python, set up a virtual environment (`venv`), install all required dependencies, and launch the web dashboard in your default browser.

---

### 🛠️ Option B: Manual Setup

1. **Create and activate a virtual environment:**
   * **Windows:**
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```
   * **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. **Install the dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Start the Dashboard:**
   ```bash
   streamlit run app.py
   ```

---

## 🗺️ Basic Canvassing & Target Compilation Workflow

1. **Core Data Ingestion:** Go to **Core Data Upload** and upload `voter_file.csv`. Map the required precinct identifier, party affiliation, and turnout history columns.
2. **Contest Classification:** Go to **Contest Data Manager** and load your Statement of Votes (SOV) file. Define the contest type and targets (e.g. Melanie Bagby vs Tom Schwedhelm).
3. **Bridge Verification:** If SOV coverage is incomplete, go to the **Ingest Crosswalk** tab and load the official cross-reference logs to realign precincts.
4. **Execution & Scoring:** Adjust weights, select the target turnout parameters, verify size guardrails, and compile/download the finalized targeting files.
