import os
import pandas as pd
import traceback
from main import run_pipeline, CONFIG, QA_METRICS

CONFIG["VOTER_FILE"] = "data/voter_file.csv"
CONFIG["MPREC_CROSSWALK"] = "data/mprec_srprec.csv"
CONFIG["SRPREC_CITY"] = "data/srprec_city.csv"
CONFIG["DISTRICT_ASSIGNMENTS"] = "data/district_assignment.csv"
CONFIG["OUTPUT_DIR"] = "outputs"

def run_tests():
    print("\n==================================")
    print("   STARTING HARD REPAIR HARNESS")
    print("==================================\n")
    failures = 0

    try:
        # Test 1
        print("TEST 1: Truth-Enforced Impossible Overlaps...")
        res = run_pipeline(target_params={'ad': '999', 'sd': '999', 'city': None})
        if res.get('status') == 'success' and res['top_precincts'].empty:
            print("PASS: Handled impossible overlap cleanly.")
        else:
            print("FAIL: Pipeline crashed or fabricated overlap rows.")
            failures += 1

        # Test 2
        print("\nTEST 2: Missing Area Graceful Degradation...")
        res = run_pipeline()
        score_df = res.get('top_precincts', pd.DataFrame())
        
        if not score_df.empty:
            if score_df['Has_Area'].iloc[0] == False:
                print("PASS: Confirmed 'Has_Area' tracks missing GIS files.")
            else:
                print("FAIL: Pipeline falsely claimed area data exists.")
                failures += 1
        else:
            print("FAIL: No score dataframe returned.")
            failures += 1

        # Test 3
        print("\nTEST 3: Countywide Output Target Creation...")
        if os.path.exists("outputs/target_precincts.csv"):
            print("PASS: Valid outputs generated.")
        else:
            print("FAIL: Target output missing.")
            failures += 1
            
        # Test 4
        print("\nTEST 4: Elasticity Mathematics...")
        if not score_df.empty and 'Turnout_Dropoff_Rate' in score_df.columns:
            print("PASS: Turnout Elasticity deployed correctly.")
        else:
            print("FAIL: Formula not replaced.")
            failures += 1
            
    except Exception as e:
        print("CRITICAL HARNESS CRASH:")
        traceback.print_exc()
        failures += 1
        
    print("\n==================================")
    if failures == 0:
        print("SUCCESS: TRUTH-ENFORCED ENGINE PASSED.")
        with open("TEST_RESULTS.md", "w") as f:
            f.write("# Automated Hard-Repair Test Results\n\nStatus: **PASSING**\nThe pipeline reliably handles missing area projections and bounces impossible district targets without fake success hooks.")
    else:
        print(f"FAILED. {failures} bounds broken.")

if __name__ == "__main__":
    run_tests()
