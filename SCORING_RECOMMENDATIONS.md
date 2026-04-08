# Scoring Recommendations

## Formula Identified Weaknesses
1.  **Fake Density:** Using `Total_Voters` entirely distorts walkability scores.
2.  **Size Bias:** `Turnout Gap` favors massively un-engaged population blocks without factoring in their historical baseline.
3.  **Two-Party Blindness:** Independent voters (NPP) dilute `Dem_Share` mathematically, punishing swing districts.

## The Corrected Priority Field Model

If the goal is to optimize volunteer deployments, we must upgrade the 3 pillars.

### 1. The Underperformance Index (Replacing "Turnout Gap")
*   **Old:** `Total_Voters - Voted_2024`
*   **New:** `(Turnout_2022 - Turnout_2024) / Total_Voters`
*   **Rationale:** We are looking for *elasticity*. Which precincts historically turned out, but are suddenly sleeping this year? A precinct that consistently never votes shouldn't be the prime target; we want the precincts that *can* vote but dropped off. Using rate delta rather than raw volume strips out the big-precinct volume bias.

### 2. True Competitiveness (Incorporating NPPs)
*   **New Formula:** `1 - abs(Dem_Share - Rep_Share)`
*   **Rationale:** Rather than calculating Dem Share against the *entire* pie (which punishes precincts with high independent populations), we calculate the strict spread between the two major field players. If Dems and Reps are perfectly tied 40-40 (with 20% NPP), the Deviation is 0, so the Competitiveness is 1.0. This specifically highlights battlegrounds irrespective of local 3rd-party flavors.

### 3. Voter Saturation (Replacing "Density")
*   **New Formula:** Since we do not have Sq Miles/Area data reliably in the voter set, we cannot calculate true "People per Sq Mile". We must abandon the explicit claim of mapping physical Density unless `geo_processor` calculates the `Area` of the polygons.
*   **The Fix:** Instruct `geo_processor.py` to extract `.area` from the `EPSG:3857` projection, map it back directly into the csv! `True Density = Total_Voters / Polygon_Area_SqMeters`. This mathematically proves Walkability!!

### Normalization Method
**Recommendation: Retain Min-Max Normalization.**
Min-Max `[0, 1]` scaling remains mathematically valid for weighting aggregations. Ensure we strictly catch divide-by-zero bounds during implementation.
