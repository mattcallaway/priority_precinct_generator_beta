# 🏰 Memory Palace: Repository Context, Architecture, & Rules

This document serves as the master "Memory Palace" of the **Priority Precinct Generator (PPG)**. It preserves deep technical design rules, mathematical equations, file profiles, and lessons learned to maintain context across sessions.

---

## 🏛️ Directory & File Registry

*   `app.py`: State machine and Streamlit dashboard interface. Manages the 6 core Tabs and file checklists.
*   `main.py`: Base pipeline engine. Aggregates demographic registers into precinct-level targets and handles geographical scoping.
*   `contest_manager.py`: Parses Statement of Votes (SOVs) and saves mapping audits.
*   `contest_signal_model.py`: Math engine for the Contest Signal Manager (preview mode). Computes type-specific rates, weights, composite score blending, and unique ranks.
*   `file_manager.py`: System file profile validator.
*   `geo_processor.py`: Spatial shapes compiler.
*   `run_audit_tests.py`: Main integration test suite (contains 10 comprehensive tests).
*   `tests/test_streamlit_app.py`: Headless Streamlit UI simulator verifying app execution.
*   `tests/fixtures/`: Contains isolated test datasets (e.g. `controlled_contest_signal_fixture.csv`).
*   `docs/`: Contains user walkthroughs, mathematical guides, and blueprints.

---

## 📜 Coding Laws & Constraints

When extending or maintaining this repository, you **MUST** adhere to the following laws:

1.  **Do Not Pollute Production Ranks**: Preview scores (`Preview_MultiContest_Composite_Score`) must reside in preview-specific dataframes/files (`preview_multi_contest_priority_scores.csv`). Never modify or pollute `outputs/final_rankings/production_priority_precincts.csv` during preview or test execution.
2.  **Strict Rejection of Test Fixtures**: Contests pointing to source files containing `tests/` or `tests/fixtures/` must be rejected/skipped in production environments, logging the warning `fixture_contest_blocked_from_non_test_run`.
3.  **Prioritize Environment Variables in Test Hooks**: The helper `is_test_mode_active()` must check `os.environ.get("PPG_RUN_MODE")`. If set to `"PRODUCTION_MODE"`, it must return `False` even if test names exist in command arguments.
4.  **No Centroid-Based GIS Joins**: When mapping precinct polygons to cities or legislative districts, always use `.representative_point()` instead of `.centroid()`. Centroids can mathematically fall outside gerrymandered, concave, or U-shaped boundaries, whereas representative points are guaranteed to fall inside polygon limits.
5.  **Clean Float Keys on Joins**: Mapped numeric columns (like `PrecinctName` or `Voting_Precinct`) read from CSV files are frequently cast by Pandas as floats. You must strip `.0` string suffixes (e.g. `40001.0` -> `40001`) during normalizations to prevent key match failures.
6.  **Secure File Copy Operations**: The file registry must verify absolute path equality (`os.path.abspath`) before performing copy operations. This prevents files from overwriting themselves in recursive loops.

---

## 🧮 Theoretical Math & Targeting Formulas

### 1. Baseline Scoring

$$P_{\text{base}} = W_t \cdot S_t + W_c \cdot I_c + W_d \cdot D$$

Where:
*   $S_t$ = **Turnout Opportunity Score**:
    *   $\text{Turnout\_Dropoff} = \max(0.0, \text{Prior\_Turnout} - \text{Current\_Turnout})$
    *   $\text{Turnout\_Expansion} = \max(0.0, \text{Target\_Turnout} - \text{Current\_Turnout})$
    *   $\text{Turnout\_Volatility} = | \text{Current\_Turnout} - \text{Prior\_Turnout} |$
    *   $$\text{Turnout\_Opportunity\_Raw} = 0.50 \cdot \text{Turnout\_Dropoff} + 0.35 \cdot \text{Turnout\_Expansion} + 0.15 \cdot \text{Turnout\_Volatility}$$
    *   $\text{Expected\_Votes\_Gained\_Adjusted} = (\text{Turnout\_Opportunity\_Raw} \cdot \text{Total\_Voters}) \cdot \min\left(1.0, \frac{\text{Total\_Voters}}{150}\right)$
*   $I_c$ = **Partisan Competitiveness Index**:
    *   $$\text{Partisan\_Competitiveness} = 1.0 - | \text{Dem\_Share} - \text{Rep\_Share} |$$
*   $D$ = **Density / Scale Score**:
    *   $\text{True\_Area\_Density} = \frac{\text{Total\_Voters}}{\text{Area\_Sq\_Miles}}$ (if shapes are loaded)
    *   $\text{Operational\_Scale\_Proxy} = \ln(1 + \text{Total\_Voters})$ (fallback)

### 2. Hardened Denominator-Aware Rates

To prevent rate dilution, the signal engine computes separate rates by contest type:
*   **Candidate Vote Share**:
    $$\text{support\_vote\_share} = \frac{\text{support\_votes}}{\text{support\_votes} + \text{opposition\_votes}}$$
*   **Registration Density**:
    $$\text{support\_registered\_rate} = \frac{\text{support\_votes}}{\text{registered\_voters}}$$
*   **Turnout Rate**:
    $$\text{turnout\_rate} = \frac{\text{ballots\_cast}}{\text{registered\_voters}}$$
*   **Ballot Measure Rate**:
    $$\text{issue\_support\_rate} = \frac{\text{issue\_support\_votes}}{\text{measure\_total\_votes}}$$

If any denominator is zero or missing, the rate outputs `NaN` with warning flags (e.g. `missing_registered_voters_denominator`), preserving truth.

### 3. Unique Ranks Sorting Order

Ranks are computed sequentially to ensure 100% uniqueness:
1.  Composite Score (Descending)
2.  Coverage (Descending)
3.  Confidence (Descending)
4.  Baseline Rank (Ascending)
5.  Precinct Name (Ascending)

---

## 🧪 Validation & Test Harness

*   **Integration Tests**: Run `python run_audit_tests.py`.
    *   Tests 1-9 cover baseline scoping, incomplete SOV warnings, PDF crosswalk parsers, and Sonoma normalization formats.
    *   Test 10 asserts all 20 of the math, weight, and safety checks on the Contest Signal Manager.
*   **UI Tests**: Run `python tests/test_streamlit_app.py` to verify the headless Streamlit dashboard render loop.
