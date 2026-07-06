# 🚶 Walkthrough & User Guide

This guide walks you through a step-by-step execution of the targeting pipeline using the Priority Precinct Generator dashboard.

---

## 🛠️ Phase 1: Core Data Upload

1. Navigate to the **📂 Central File Manager** or **1. Core Data Upload** tab.
2. Upload your voter database file as **`voter_file.csv`** (CSV format).
3. Once loaded, expand **`🗺️ Voter File Column Mapping (Confirm / Override)`**:
   * Verify that the dropdowns for `PrecinctName` and `Party` columns are correctly mapped to your file's headers.
   * Map the `Turnout 2024` and `Turnout 2022` columns.
   * If your voter file includes district columns directly (e.g. Supervisorial or Assembly Districts), select them in the **Optional Geographic Districts** section. If not, leave them as `None (Auto-detect)`.

---

## 🗳️ Phase 2: Contest Data Management & Classification

To run a production-ready targeting list, you must provide real election results to guide the priority scores.

1. Go to the **4. Contest Data Manager** tab.
2. Upload your Statement of Vote (SOV) file (e.g., `detail.csv`).
3. Under **Precinct Column Mapping**, select the header in your CSV that identifies the precincts (e.g., `Precinct`).
4. **Define your Contest Targets:**
   * Enter a descriptive **Contest Name** (e.g., `Supervisor D4 Primary`).
   * Select the **Contest Type**:
     * **Candidate:** Compares a Favorable Candidate vs. an Opponent.
     * **Initiative:** Tracks YES vs. NO margin.
     * **Turnout:** Evaluates overall turnout percentages.
   * Choose the **Influence Target**: Choose whether this contest adjusts the precinct's *Support Score*, *Persuasion Score*, *Turnout Score*, *Issue Alignment Score*, or is a *Confidence Only* indicator.
   * Select your **Favorable Column** (e.g. `MELANIE BAGBY - Total Votes`) and **Opposition Column** (e.g. `TOM SCHWEDHELM - Total Votes`).
   * Click **➕ Add Contest to Scoring Model**.

---

## 🌍 Phase 3: Geographic Boundary Setup (Optional)

If you wish to constraint your final report to specific legislative boundaries (such as a specific supervisorial district or assembly district):

1. **Voter-File Extraction:** The engine will automatically check if the voter file has direct district fields mapped.
2. **Sonoma County Rule:** If you are targeting Sonoma County and your voter file does not have supervisorial columns, check the **"Derive Sonoma Supervisorial District from PrecinctName prefix"** sidebar setting. This automatically infers the district from the leading digit (e.g., precinct `440001` -> Supervisorial District 4).
3. **Shapefile Spatial Joins:** Upload matching boundary shapefiles (in `.zip` format) under **City Assignment Manager** or **Legislative District Manager** to automatically calculate city and district lines.

---

## 🚀 Phase 4: Execution & Weighting

1. Go to the **5. Execution & Results** tab.
2. Review the **Geography Sources Engaged** table to verify where supervisorial, assembly, and city data is being pulled from.
3. Review the **Pipeline Readiness Status**:
   * If contest data is loaded and classified, you will see a green **Production Ranking Ready** status.
   * If contest data is missing, the execution button will be locked.
4. Adjust the weights in the sidebar:
   * **Turnout Opportunity Weight:** Focuses on precincts with high voter turnout opportunity (dropoff, expansion, and volatility).
   * **Partisan Competitiveness Weight:** Highlights politically balanced precincts.
   * **True Area Density / Operational Scale Proxy Weight:** Elevates precincts with high voter concentrations or operational scale.
   * **Contest Data Influence Weight:** Adjusts how heavily your uploaded election results influence the final priority ranks.
5. Define the **Turnout Opportunity Settings** in the sidebar:
   * **Election Context:** Select General (`75%` target), Midterm (`65%` target), Primary (`45%` target), Special (`35%` target), or Other.
   * **Override Target Turnout:** Provide a manual turnout benchmark.
   * **Enforce Tiny Precinct Size Guardrail:** Check to penalize small precincts (< 150 voters) so they do not artificially dominate ranks.
6. Click **🚀 Execute Production Precinct Scoring**.

---

## 📊 Phase 5: Exporting & Analyzing Targeting Sheets

Once execution completes, download your targeting reports:
* **📥 Production Final Rankings (CSV):** Your master targeting list. All scores, normalizations, and rankings are calculated **within your selected geographic universe**.
* **📥 Rank Shift Report (CSV):** Identifies which precincts jumped or fell in priority once candidate support was layered in.
* **📄 Normalization Audit (CSV):** Located in `outputs/contest_data_manager/precinct_normalization_audit.csv`. Logs raw vs normalized precinct transformations to trace matching.
