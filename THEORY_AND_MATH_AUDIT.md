# Theory & Math Audit

## A. Mathematical Consistency & Soundness
**Status: BROKEN / MISLEADING**

*   **Weakness 1: "Density" is Fake.**
    We heavily weight "Density" (20%), but the formula calculates: `voter_norm = min_max_norm(df['Total_Voters'])`. Total population is not density. A 100-square-mile rural precinct with 2,000 voters will outscore a 0.5-square-mile downtown precinct with 1,500 voters under this model. **Field campaigns die on commute times.** By classifying raw magnitude as density, the model practically guarantees volunteers will be sent to the least walkable turfs available simply because they are large.
*   **Weakness 2: Competitiveness Distorts Reality.**
    The formula: `1 - abs(Dem_Share - 0.5) * 2`.
    This assumes a strict 2-party vacuum. It treats a precinct that is 45% Dem, 45% Rep, and 10% NPP completely identically to a precinct that is 45% Dem, 5% Rep, and 50% NPP. The strategic walkability of those two precincts for a Democratic campaign is wildly divergent, but the engine scores them exactly the same because `Dem_Share` isolated the 45% exclusively.
*   **Weakness 3: High-Floor Bias on Turnout.**
    `Turnout Gap = Total_Voters - Voted_2024`.
    Very large precincts essentially pre-dominate the Turnout Gap because the raw numerical un-voted counts are necessarily higher than tiny precincts, even if the tiny precinct has a horrible 30% participation rate and the large one has 90%. We are scoring sheer magnitude twice (once in Density, once in Turnout Gap), severely over-weighting raw geographical size.

## B. Auditability
*   **Status: Passable but fragile.** `core_diagnostics.py` successfully intercepts the intermediate variables across `07_scoring_breakdown.csv`. However, because the raw "Turnout Rate %" isn't explicitly printed next to the "Turnout Gap" raw count, verifying *why* the normalized gap is huge takes manual calculator work.

## C. Reality vs Model Verdict
The model is **strategically naive**. It is overly obsessed with "Big Precincts". It double-counts size as a primary driver for priority while obscuring third-party spoiler variables. Field directors utilizing this list would experience shockingly bad contact-rates-per-hour on the doors.
