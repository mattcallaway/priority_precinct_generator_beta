# 🚶 User Walkthrough & Operations Guide

This guide provides a detailed step-by-step walkthrough of the Priority Precinct Generator (PPG) system. It outlines how to ingest voter data, configure campaign profiles, classify Statement of Votes (SOVs), compile official precinct bridges, run preview scoring models, and execute production targets.

---

## 📂 Phase 1: Core Data Upload

1. **Access the Dashboard**: Start the Streamlit application (`streamlit run app.py`) and navigate to **"📂 Central File Manager"** or the **"1. Core Data Ingestion"** tab.
2. **Upload the Voter Database**: Drag and drop your voter file. The system registers it as `voter_file.csv`.
3. **Map Demographic Fields**: Expand the mapping accordion and match the dropdowns to your file's headers:
   * **Precinct Identifier**: e.g., `PrecinctName` or `PRECINCT`.
   * **Party Composition**: e.g., `Party` or `PARTY_CODE`.
   * **Voter History**: Map the `Turnout 2024` (current) and `Turnout 2022` (prior) history columns to extract turnout drop-off, expansion, and volatility.
4. **Geographic Districts**: Map legislative district fields (e.g. supervisorial, congressional, or assembly districts) if they are explicitly present. If not, set them to `None (Auto-detect)` to let the spatial boundary engines infer them.

---

## 🗳️ Phase 2: Contest Data Ingestion & Classification

1. **Access Tab 4 ("4. Contest Data Manager")**: This tab is the gateway to production-mode targeting.
2. **Upload Statement of Votes (SOV)**: Upload your local SOV returns spreadsheet (e.g., `detail.csv`). The file parser automatically cleans hierarchical multi-level headers.
3. **Classify Columns**:
   * Map the SOV precinct column (e.g., `Precinct`).
   * Select a target **Contest Name** (e.g., `Supervisor D4 Melanie Bagby vs Tom Schwedhelm`).
   * Define the **Contest Type**:
     * `Candidate`: Elect a favorable candidate over an opponent.
     * `Ballot Measure`: Pass or defeat a specific initiative.
     * `Turnout Only`: Optimize targets purely based on real-world voter turnout volumes.
     * `Partisan Baseline`: Map a partisan baseline contest to evaluate underlying political trends.
   * Assign Column Roles: Select which column represents **Support** (e.g. `MELANIE BAGBY - Total Votes`), **Opposition** (e.g. `TOM SCHWEDHELM - Total Votes`), **Registered Voters**, or **Ballots Cast**.
   * Define **Scoring Influence**: Decide which demographic component this contest adjusts (`Support Score`, `Persuasion Score`, `Turnout Score`, `Issue Alignment Score`, or `Confidence Only`).
   * Click **➕ Add Contest to Scoring Model** to update `contest_classification_config.json`.

---

## 🌍 Phase 3: Spatial Shapefile Boundaries

If you are targeting a legislative district but your voter database lacks district headers:

1. **Upload District Geographies**: Under **"3. Legislative District Manager"** or **"2. City Mapping Manager"**, upload zipped shapefile packages (containing `.shp`, `.shx`, `.dbf`, and `.prj` files).
2. **Representative Point Intersects**: The spatial compiler (`geo_processor.py`) extracts representative coordinate coordinates:
   * Unlike centroids (which can fall outside irregularly shaped boundary curves), the `representative_point()` guarantee ensures polygon coordinates fall strictly within boundary bounds.
   * Auto-generates local mappings (`data/district_assignment.csv`).
3. **Null Fallbacks**: Precincts falling outside mapped municipalities are automatically assigned to the `"Unincorporated"` boundary group, preserving counts.

---

## 🌉 Phase 4: Official Precinct Crosswalk Compiler

Statement of Votes (SOVs) are published by election clerks at the *voting precinct* level, which typically aggregates multiple regular *voter registration precincts*. To prevent data loss or scoring skew:

1. **Upload Cross-Reference PDFs**: In Tab 4 (or Tab 6), upload the official Registrar of Voters PDF crosswalks:
   * **Regular to Voting PDF**: e.g., `ewmr010_regabsvotpctxref_2026-06-02.pdf`
   * **Voting to Regular PDF**: e.g., `ewmr008_votabsregpctxref_2026-06-02.pdf`
2. **Execute Crosswalk Builder**: Click **Build Canonical Crosswalk**. The PDF parser sweeps lines and builds a coordinate grid to compile the bidirectional link matrix:
   * Saves compilation to `outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk.csv`.
3. **Signal Allocation Rules**:
   * **Exact Matches**: Retain raw vote counts (e.g. `support_votes = 150`, `opposition_votes = 50`) and enjoy 100% confidence.
   * **Inherited Matches (Child Precincts)**: Receive the parent's calculated percentages (e.g., support rate = 75%), but raw vote totals are left blank (`NaN`) to prevent double-counting when campaigns roll up targeted list totals. Confidence is scaled down dynamically ($C_{\text{child}} = 0.90 \cdot C_{\text{parent}}$).

---

## 📈 Phase 5: Multi-Contest Signal Manager (Tab 6 Preview Mode)

Tab 6 (**"📈 6. Contest Signal Manager"**) is designed to run preview scoring simulations without polluting the official production rankings:

1. **Configure Campaign Profile**: Set your campaign goal (e.g., `Elect candidate`, `Pass measure`, `Increase turnout`), candidate names, and date.
2. **Library Registry**: Review your active library. Toggle checkboxes to disable/enable individual contests or adjust their weights:
   * **Contest Weight**: Scales how heavily a specific contest's returns contribute to the composite score.
   * **Confidence Weight**: Adjusts how heavily a contest's matching rate impacts the composite confidence score.
3. **Run Multi-Contest Modeling**:
   * Calculates candidate vote shares, registration densities, and turnout margins.
   * Aggregates active components into `Preview_Contest_Component`.
   * Melds it with baseline scores into `Preview_MultiContest_Composite_Score`.
   * Flags missing denominators (`missing_vote_share_denominator` etc.) and flags impossible rates ($>1.0$ on non-odds-ratios).
4. **Deterministic Preview Ranks**: Ranks target precincts uniquely from $1 \dots N$ by sorting sequentially:
     1. Composite Score (Descending)
     2. Coverage (Descending)
     3. Confidence (Descending)
     4. Baseline Rank (Ascending)
     5. Precinct Name (Ascending)
5. **Preview Visualizations**:
   * **Preview Rankings Table**: Review the deterministic targeting hierarchy.
   * **Targeting Scatter Plot**: Visualizes Precinct Base Score vs. Contest Enrichment Score, colored by strategic targeting buckets:
     * *Strong support / high turnout*
     * *Strong support / low turnout* (Optimal Mobilization)
     * *Persuasion opportunity*
     * *Opposition / high turnout*
     * *Opposition / low turnout*
   * **Correlation Matrix**: Displays Pearson correlation coefficients between contest columns to spot overlapping trends.

---

## 🚀 Phase 6: Production Execution

1. Navigate to Tab **"5. Execution & Results"**.
2. **Readiness Audit**: Ensure the pipeline status shows a green **Production Ready** verdict. If contest data or official crosswalk files are missing, the generator blocks execution to prevent incomplete targets from reaching the field.
3. **Weight Adjustments**: Set the weights in the sidebar:
   * *Turnout Opportunity Weight*: Mobilizes high-potential drops.
   * *Partisan Competitiveness Weight*: Focuses on major-party swing margins.
   * *Density/Operational Scale Weight*: Directs volunteers to physically clustered voter hubs.
   * *Contest Influence Weight*: Blends baseline scores with active election returns.
4. **Trigger Generation**: Click **🚀 Execute Production Precinct Scoring**. The engine compiles scores, runs final guardrails (tiny precinct penalization), and exports targeting packages.

---

## 📥 Phase 7: Export Manifest & Diagnostic Logs

Upon completion, all targeting reports and validations are compiled into a ZIP archive under `outputs/final_downloads/`:
* `production_priority_precincts.csv`: The official targeting list.
* `base_preview_rankings.csv`: Demographic baseline targeting.
* `top_50_explainability_table.csv`: Traceability log for the top 50 targets.
* `rank_shift_report.csv`: Shift metrics showing the impact of contest returns.
* `contest_scope_validation.md`: Compliance report evaluating data coverage.
* `precinct_normalization_audit.csv`: Row-by-row log of precinct naming conversions.
* `readiness_contradiction_report.md`: Safeguard matrix verifying configurations.
