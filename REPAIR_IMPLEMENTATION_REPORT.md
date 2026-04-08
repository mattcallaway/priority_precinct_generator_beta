# Repair Implementation Report

This document records the exact repairs made to the codebase to strip away fake proxies, hardcoded magic, and UI spoofing. The core directive was: **Never invent completeness.**

## 1. Parameterization over Hardcoding
*   **Old Behavior:** `main.py` explicitly hardcoded `Assembly_District == 12` and `Supervisorial_District == 2`. It would silently output these to a target file regardless of what the user uploaded.
*   **Repaired Behavior:** `main.py` now accepts a dynamic `target_params` dictionary. The UI `app.py` physically reads the available districts from the joined `district_assignment.csv` and populates a dropdown, forcing the user to select the subset. If an impossible overlap is requested (yielding a 0-row Dataframe), the UI triggers a strict `error()` blocking state instead of rendering a fake success animation over empty sheets.

## 2. Dependency Truths Enforced
*   **Old Behavior:** Density was calculated unconditionally using raw `Total_Voters` as a proxy, despite that just being a population count. `Turnout_Gap` was calculated unconditionally, punishing large precincts simply for existing.
*   **Repaired Behavior:** 
    *   **Area Extraction Mechanism:** `geo_processor.extract_precinct_metrics()` was built safely parsing the precinct shapefiles using `EPSG:5070` (Equal Area Projection). It calculates the square mileage mathematically and creates `srprec_metrics.csv`.
    *   **UI Capability Locks:** If `srprec_metrics.csv` does not exist, the physical `Area` is considered missing. `app.py` actively disables the "True Density" slider, greying it out and explicitly placing a cross icon beside it stating: `Unavailable: Missing Shapefile Area Polygons`. The same capability lockdown was bound to "Turnout Elasticity" if `General22` turnout history does not exist in the source upload.
    
## 3. Radical Outputs Transparency
The 12-file audit log architecture was preserved but heavily hardened. `07_scoring_breakdown.csv` now explicitly captures the logical state of every precinct using dependency booleans (`Has_Area`, `Has_Prior_Turnout`, `Used_Density`). `10_pipeline_summary.txt` explicitly documents whether the final ranking represents a Partial Confidence or Full Confidence run.
