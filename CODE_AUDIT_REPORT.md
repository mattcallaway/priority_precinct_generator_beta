# Code Quality Audit Report

## Critical Failures (Must Fix Immediately)
1.  **Silent Failures in Input Loading (`main.py:43`):** 
    - `city_df` and `dist_df` loading use raw `try/except` blocks that just drop `inputs['city'] = None`. If the file is badly malformed, it doesn't crash; it just builds an empty pipeline. The user thinks it succeeded.
2.  **Unsafe Null Propagations (`main.py:277`):**
    - `total_party = df['Dem'] + df['Rep'] + df['NPP'] + df['OtherParty']`
    - If a voter file uses different casing for parties and misses the mapping, these sums become `0`.
    - `df['Dem'] / total_party.replace(0, np.nan)` generates `NaN` Dem_Share, which completely obliterates the Competitive Index calculation.

## High Priority Fixes (Structural Bugs)
3.  **UI Leaking into Core Logic (`app.py:165` & `230`):**
    - The `geo_processor.py` is invoked directly inside Streamlit button callbacks, and it bypasses `main.py`'s QA matrix. The UI is doing data engineering instead of acting purely as a view layer.
4.  **Fake UI Success States (`app.py:269`):**
    - The UI calls `st.snow()` and displays "✅ Analysis Complete!" just because `main.py` returned a dictionary. It does not actually assert that `result['top_precincts']` isn't entirely empty. It congratulates the user for creating a 0-row targeting list.

## Medium Cleanup (Code Laziness)
5.  **Hardcoded Target Geographies:**
    - `overlap_df` in `main.py` statically hardcodes `Assembly_District == 12` and `Supervisorial_District == 2`. While this serves the AD12/SD2 goal, it's hardcoded directly into the master `export_outputs()` engine, meaning this engine is fundamentally unusable for any other campaign unless they explicitly open the python file and edit line 320. This should be a dynamic filter parameter passed down from `app.py`.
6.  **Normalization Divide-By-Zero (`main.py:293`):**
    - `(series - series.min()) / (series.max() - series.min())`
    - The code attempts to catch `max == min` but just returns `pd.Series(0)`. This destroys mathematical distribution.

## Nice To Have / Best Practices
7.  **State Management Cleanup:**
    - `os.makedirs()` calls are sprayed randomly across headers in `app.py` and `main.py`. These belong in a strictly executed init function.
