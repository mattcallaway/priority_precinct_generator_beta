# Priority Precinct Generator (Beta)

Welcome to the automated pipeline for the **Priority Precinct Generator**. This tool evaluates raw campaign data alongside precinct-level geographies to identify exactly where your field program can achieve tactical advantages.

This project is entirely local, ensuring 100% data security. **It features a smart, highly-usable Drag-and-Drop Data Dashboard designed to ingest messy data, automatically route missing gaps through dynamic GIS processing, and produce rigorous 12-file QA audits.**

---

## 🚀 Getting Started

The application no longer requires manual command-line typing. 

1. **Ensure Python is installed:** Download from [python.org](https://www.python.org/downloads/) (Make sure to check "Add Python to PATH" during the install wizard!).
2. **Launch the Engine:**
   - On Windows: Double-click **`run_generator.bat`**
   - On Mac/Linux: Double-click **`run_generator.sh`**

The first boot will securely download necessary math and mapping dependencies locally. A sleek web dashboard will then automatically appear in your browser.

---

## 🗺️ Using the 4-Tab Sourcing Roadmap

The application acts as a step-by-step concierge guiding you to perfectly format campaign data logic. You do *not* need to start with perfectly formatted mapping tables.

### 1. 📁 Core Uploads
Begin by uploading your baseline Voter Matrix.
* **`voter_file.csv`**: Exported directly from your central Voter Database (NGP VAN / PDI / L2). Needs baseline demographics and voting history.
* **`mprec_srprec.csv`**: The "Crosswalk". Request this directly from your County Registrar of Voters (ROV) office. It maps arbitrarily small database-level precincts to master County map precincts.

### 2. 🏙️ City Mapping Manager
Your final export should contain City names so field organizers know where to dispatch volunteers easily. 
If you don't have a mapping file indicating which precinct corresponds to which city:
* **The Geospatial Autobuilder**: Download your *City Boundaries Shapefile* from your local County Open GIS Data portal or the US Census Bureau TIGER line website. Zipped it. Drop it alongside your zipped *Precinct Shapefile*, and the dashboard will mathematically crunch the lines and figure out what city every precinct lives in natively.
* **The Template Method**: Click "Generate Excel Template" and manually type the cities into a pre-populated list if you prefer traditional data-entry.

### 3. 🗺️ Legislative District Manager
Your field efforts likely target an explicitly overlapping boundary (e.g. State Assembly 12 intersecting Supervisor District 2).
If your voter database doesn't export these district columns natively:
* **The Geospatial Autobuilder**: Again, download the *Legislative Boundaries Shapefile* directly from your local state redistricting site. Zip them, and upload them. The app will intersect the map boundaries seamlessly and assign districts automatically without ever launching QGIS.

### 4. ✅ Execution & Priority Configuration
Once your Dashboard Status Panel shows all Green validations, use the sliders to configure your exact mathematical Campaign priority. **Note: Sliders are strictly truth-enforced.** The *True Density* slider will be disabled if you have not extracted Physical Area from Shapefiles. *Turnout Elasticity* will be disabled if your Voter File lacks prior-cycle history. Once your parameters are set and target districts are dynamically chosen from the dropdowns, hit **Execute Precision Scoring**.

---

## 📦 The 12-File Diagnostic Export System

Instead of a "black box" giving you an Excel file you blindly trust, the engine generates an explicit, auditable folder `outputs/run_TIMESTAMP/` locally on your computer upon every execution containing 12 critical files:

**1. The Audit Log**
* `10_pipeline_summary.txt`: A plain-English reading. Use this to verify Match Rates (Are we missing >5% of our mapping routes?) and see top targets explicitly.

**2. The Mathematical Integrity Breakdowns**
* `07_scoring_breakdown.csv`: Shows the *exact* Normalized formulas side-by-side for every single precinct.
* `12_score_distribution.csv`: A frequency histogram of Priority Scores to detect if mathematical skews are grouping targets unnaturally.

**3. The Join Tracking & QA (To find logic gaps)**
* `11_join_diagnostics.csv`: Exact matrices of input rows vs matched rows vs unmatched rows for every database join.
* `03_unmatched_mprec.csv` & `06_unmatched_districts.csv`: Did a piece of the map fail to draw? Was a sub-precinct missing from your ROV crosswalk? These explicitly output *which* rows failed so you can instantly patch them in your source database.
* File `01`, `02`, `04`, and `05` provide sample snapshots of the raw grouped datasets exactly before scoring execution for maximum operational transparency.

**4. The Final Master Targets**
* `09_target_overlap.csv`: The pure, aggressively targeted overlapping precincts ready to be knocked exactly based on the dynamic subset parameters selected in the execution UI.

---

### Technical Deep Dive
For a flowchart outlining exactly how the python `geo_processor` coordinates physical Representative Bounds alongside the analytics engine to execute these commands, read `technical_map.md` in the parent directory!
