import os
import sys
sys.path.insert(0, os.path.abspath("venv/Lib/site-packages"))
sys.path.append(os.path.abspath("."))

import pandas as pd
from main import run_pipeline, CONFIG

CONFIG["VOTER_FILE"] = "data/voter_file.csv"
CONFIG["MPREC_CROSSWALK"] = "data/mprec_srprec.csv"
CONFIG["SRPREC_CITY"] = "data/srprec_city.csv"
CONFIG["DISTRICT_ASSIGNMENTS"] = "tests/fixtures/district_assignment.mock.csv"

try:
    print("Running pipeline...")
    res = run_pipeline(target_params={'ad': '999', 'sd': '999', 'city': None}, allow_mock=True)
    print("Success! Status:", res.get("status"))
except Exception as e:
    import traceback
    traceback.print_exc()
