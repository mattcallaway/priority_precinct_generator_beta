# Test Plan

## The "Trust But Verify" Runner
I will build `run_audit_tests.py`. It will completely bypass Streamlit (`app.py`) to isolate programmatic logic and prove the underlying data pipelines cannot be subverted.

### Phase A: Smoke Tests
- Initialize pipeline with `CONFIG` overridden to point to explicit mock files.
- Ensure the pipeline completes successfully without unhandled tracebacks.

### Phase B: Integrity Tests
These tests will specifically hunt the exact flaws surfaced in `CODE_AUDIT_REPORT.md` and `AUDIT_DRIFT_REPORT.md`.
1.  **Voter Math Law:** `assert Voted_2024 <= Total_Voters`
2.  **Partisan Law:** `assert Dem + Rep + NPP + OtherParty == Total_Voters`
3.  **Density Law:** `assert True_Density > 0` (Requires area injection implementation)

### Phase C: Failure Mode Tests
- Intentionally pass a scenario where all precincts have exactly 100 voters.
- Ensure `Turnout_Gap` normalization doesn't throw a `ZeroDivisionError` or wipe out the scores.
- Intentionally pass a scenario where 2 MPRECs are dropped from the crosswalk.
- Assert that `run_pipeline()['warnings']` specifically logs `< 95% threshold hit`.
