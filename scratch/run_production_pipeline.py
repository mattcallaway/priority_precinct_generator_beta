import os
import sys
import pandas as pd
import json

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("venv/Lib/site-packages"))

from main import run_pipeline

def run_production():
    res = run_pipeline(
        weights={'turnout_gap': 0.4, 'competitive_index': 0.4, 'density': 0.2},
        target_params={'ad': None, 'sd': None, 'city': None},
        allow_mock=False,
        contest_file_path="data/detail.csv",
        contest_prec_col="Precinct",
        contest_influence_weight=0.3,
        allow_low_coverage_contest=True,
        override_scope_mismatch=True,
        scope_override_confirmed=True
    )
    print("Full result:", json.dumps(res, indent=2) if isinstance(res, dict) else res)
    print("Pipeline run result:", res.get("status"), res.get("verdict"))

if __name__ == "__main__":
    run_production()
