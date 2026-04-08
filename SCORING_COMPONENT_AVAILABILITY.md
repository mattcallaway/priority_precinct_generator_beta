# Scoring Component Availability

This engine is built upon three priority pillars. If data required to calculate a pillar is missing, the engine does not "guess" – it permanently excludes the parameter from execution.

### Pillar 1: Turnout Elasticity
*   **Formula:** `(Voted_Prior - Voted_Current) / Total_Voters`
*   **Availability Protocol:** Requires the `voter_file.csv` to harbor a historical field equivalent to `'general22'`.
*   **State if Disabled:** The algorithm completely zeroes out this multiplier. Weighting shifts entirely to Competitiveness and Density. No fallback "Turnout Gap" is applied to prevent size-distortions.

### Pillar 2: True Competitiveness
*   **Formula:** `1.0 - absolute(Dem_Share - Rep_Share)`
*   **Availability Protocol:** Always fully available as long as base voter files have a 'party' column mapping. It exclusively looks at Major Party tension, safely circumventing Independent (NPP) dilution math.
*   **State if Disabled:** N/A (Hard-fails on data ingest if party column is entirely absent).

### Pillar 3: Voter Volume Density
*   **Formula:** `Total_Voters / Area_Square_Miles`
*   **Availability Protocol:** Must extract `.area` from mapping polygons dynamically using `EPSG:5070` Equal Area mapping projections inside `geo_processor.py`.
*   **State if Disabled:** Rather than falling back to `Total_Voters` (which explicitly mislabels Population Size as Density), the entire metric is locked out. A warning is dropped gracefully into the `10_pipeline_summary.txt`.
