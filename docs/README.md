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

### 1. Installation
Install python dependencies in your virtual environment:
```bash
pip install -r requirements.txt
```

### 2. Start the Dashboard
Launch the Streamlit web dashboard:
```bash
streamlit run app.py
```

### 3. Basic Target Compilation Workflow
1. **Core Data Upload:** Navigate to **Core Data Upload** and upload `voter_file.csv`. Confirm or adjust the detected column mappings (such as PrecinctName, Party, and Turnout history).
2. **Load Contest File:** Upload your Statement of Vote (SOV) file (CSV/XLS/XLSX) in **Contest Data Manager**.
3. **Map and Classify:** Classify the contest type (Candidate, Turnout, or Initiative) and map the precinct identifier column. Define your target candidate columns (e.g. Melanie Bagby vs Tom Schwedhelm).
4. **Review Geography:** If using shapefiles or external mappings, upload them in their respective tabs.
5. **Score:** In **Execution & Results**, define component weights, choose your election context (General, Primary, Midterm, or Special), configure the tiny precinct guardrails, and run the engine to download the final targeting reports!
