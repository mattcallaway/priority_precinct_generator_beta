# Drift Audit Report

## Core Purpose Restatement
The sole purpose of the Priority Precinct Generator is to:
**Take messy local campaign voter data and precinct mapping inputs, reliably transform them into a transparent, auditable, ranked precinct list for field targeting, especially for overlapping district geographies like Assembly District 12 and Supervisorial District 2.**

## A. Purpose Drift
*   **The UI "Magic" Trap:** The UI allows users to bypass hard data validation relying entirely on shapefile "auto-generation" toggles. This optimizes for "looking cool" while running spatial joins in the back, silently pushing massive untested geographic assumptions right into the scoring model without forcing human verification on the crosswalks first.
*   **Decorative Explanations:** The `debug_explainer.txt` writes out hardcoded strings telling the user what the math is *assumed* to be, rather than logging what the math *actually executed*. It feels like a diagnostic, but is largely static copy.

## B. Documentation Drift
*   **Aspirational Feature Descriptions:** The `README.md` describes the `Min-Max` execution flawlessly, but the reality is our `voter_norm` min-max execution fails if all precincts happen to have the exact same total voters (resulting in a Divide By Zero unhandled drop-off).
*   **Fake QA Promises:** The walkthrough acts as if `srprec_city.csv` failures generate a hard stop. In reality, `main.py` just swallows `Failed to load city mapping` and assigns `None`, allowing the model to produce a spreadsheet with blank city domains, breaking the promised strict format.

## C. Theory Drift
*   **Misleading "Density":** The app calculates `Density` simply using raw `Total_Voters`. This is population *size*, not Density. True density requires Area. We are heavily favoring gigantic suburban/rural tracts just because they hold 10,000 spread-out voters, actively punishing dense, walkable urban apartment blocks holding 1,500 voters. The theory drifted away from "walkability" into purely "volume".

## D. QA Drift
*   **Silent Propagations:** The UI success screen ("✅ Analysis Complete!") triggers even if `score_df` returns 0 valid overlap rows.
*   **No Crash Recovery Logs:** If the Pandas index is broken, the app just throws a generic `error` status dict string while keeping the front-end dashboard green and pretty. 

**Verdict:** The system traded rigorous enforcement for a frictionless UX. It drifted into becoming a flashy demo that swallows errors to look "ready".
