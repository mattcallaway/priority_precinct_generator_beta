# 🧮 Mathematical & Targeting Theory Explainer

This document outlines the underlying math, formulas, and targeting models used by the Priority Precinct Generator.

---

## 1. Demographic Baseline Scoring Components

When evaluating precincts based on `voter_file.csv` alone, PPG calculates three core demographic metrics:

### A. Turnout Opportunity Score
Instead of generic turnout elasticity, PPG calculates **Turnout Opportunity** to target precincts where campaigns can maximize vote gains:

$$Current\_Turnout = \frac{\text{Voted\_Current}}{\text{Total\_Voters}}$$
$$Prior\_Turnout = \frac{\text{Voted\_Prior}}{\text{Total\_Voters}} \quad (\text{if history is available; otherwise NaN})$$

Using these, we calculate:
* **Turnout Dropoff:** The portion of voters who voted in the prior cycle but missed the current one.
  $$\text{Turnout\_Dropoff} = \max(0.0, \text{Prior\_Turnout} - \text{Current\_Turnout})$$
* **Turnout Expansion:** The difference between a benchmark target turnout ($Target\_Turnout$) and the current turnout.
  $$\text{Turnout\_Expansion} = \max(0.0, \text{Target\_Turnout} - \text{Current\_Turnout})$$
* **Turnout Volatility:** The absolute variance between cycles.
  $$\text{Turnout\_Volatility} = | \text{Current\_Turnout} - \text{Prior\_Turnout} |$$

The raw turnout opportunity value is defined as:
$$\text{Turnout\_Opportunity\_Raw} = 0.50 \times \text{Turnout\_Dropoff} + 0.35 \times \text{Turnout\_Expansion} + 0.15 \times \text{Turnout\_Volatility}$$

If prior turnout history is missing, we bypass drop-off and volatility, defaulting strictly to:
$$\text{Turnout\_Opportunity\_Raw} = \text{Turnout\_Expansion}$$

#### Target Turnout Benchmarks
The default benchmark $Target\_Turnout$ depends on the election context:
* General Election: `0.75`
* Midterm Election: `0.65`
* Primary Election: `0.45`
* Special Election: `0.35`
* Other: `0.45`

### B. Tiny Precinct Guardrail & Expected Votes Gained
To calculate actual operational target value, we compute the number of votes a campaign can expect to expand:
$$\text{Expected\_Votes\_Gained} = \text{Turnout\_Opportunity\_Raw} \times \text{Total\_Voters}$$

To prevent tiny precincts (which might have high percentage opportunity due to low sample size) from ranking at the top, a **Size Factor** guardrail is applied:
$$\text{Size\_Factor} = \min\left(1.0, \frac{\text{Total\_Voters}}{150}\right)$$
$$\text{Expected\_Votes\_Gained\_Adjusted} = \text{Expected\_Votes\_Gained} \times \text{Size\_Factor}$$

The min-max normalized value of `Expected_Votes_Gained_Adjusted` determines the final `Turnout_Opportunity_Score`. Any precinct with `Total_Voters < 50` is marked as `"too_small"` under the `Viability_Flag`.

### C. Partisan Competitiveness
Partisan Competitiveness measures the political balance between the two major parties:

$$\text{Dem\_Share} = \frac{\text{Dem}}{\text{Dem} + \text{Rep}}$$
$$\text{Rep\_Share} = \frac{\text{Rep}}{\text{Dem} + \text{Rep}}$$

$$\text{Partisan\_Competitiveness} = 1.0 - | \text{Dem\_Share} - \text{Rep\_Share} |$$

If a precinct has zero registered major party voters, `Partisan_Competitiveness` is set to `NaN` and filled with `0.0` during normalization.

### D. True Area Density vs. Operational Scale Proxy
Canvassing efficiency is related to geography:
* **True Area Density (If shapefiles are loaded):**
  $$\text{True\_Area\_Density} = \frac{\text{Total\_Voters}}{\text{Area\_Sq\_Miles}}$$
* **Operational Scale Proxy (Fallback if GIS data is missing):**
  To prevent large precincts from dominating, we scale size logarithmically:
  $$\text{Operational\_Scale\_Proxy} = \ln(1 + \text{Total\_Voters})$$

---

## 2. Base Priority Score & Scoping Calculations

PPG calculates demographic baseline scores across two distinct scopes:

### A. Countywide Scoped Scores
Raw columns are normalized across all precincts countywide to yield:
* `Countywide_Base_Priority_Score`
* `Countywide_Base_Rank`

### B. Selected Universe Scoped Scores
Raw columns are normalized *only* within the filtered target subset (e.g. Supervisorial or Assembly boundaries) to yield:
* `Selected_Universe_Base_Priority_Score`
* `Selected_Universe_Base_Rank`

The primary export uses the universe-scoped metrics:
$$\text{Base\_Priority\_Score} = \text{Selected\_Universe\_Base\_Priority\_Score}$$
$$\text{Base\_Rank} = \text{Selected\_Universe\_Base\_Rank}$$

$$\text{Base\_Priority\_Score} = (W_{TO} \times \text{Turnout\_Opportunity\_Score}) + (W_{PC} \times \text{Partisan\_Competitiveness\_Score}) + (W_{OS} \times \text{Density\_Component})$$

---

## 3. Component-Level Contest Enrichment

When Statement of Votes contest records are added, they are grouped into component categories:
* **Contest Support Score:** Candidate or ballot measure favorable share.
* **Contest Persuasion Score:** Competitiveness/margin indicators.
* **Contest Turnout Score:** Real-world turnout percentages.
* **Contest Issue Alignment Score:** Measure yes/no margin splits.

The final enrichment score is the average of these active components:
$$\text{Contest\_Enrichment\_Score} = \text{mean}(\text{Active Components})$$

* **Unmatched Fallback:** If a precinct has no matching contest row, its `Contest_Enrichment_Score` is `NaN`, its coverage flag is `"no_contest_match"`, and its final priority score remains exactly equal to its demographic base priority score:
  $$\text{Final\_Priority\_Score} = \text{Base\_Priority\_Score}$$
* **Confidence Only:** Contests mapped as "Confidence Only" are excluded from direct score influence, contributing only to the `Contest_Confidence` indicator.

$$\text{Final\_Priority\_Score} = (1.0 - W_{\text{influence}}) \times \text{Base\_Priority\_Score} + W_{\text{influence}} \times \text{Contest\_Enrichment\_Score} \quad (\text{if matched})$$
