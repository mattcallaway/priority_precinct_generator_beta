import os
import shutil
import json
import pandas as pd
import sys
import random

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Inject project root and venv site-packages
project_root = r"c:\Users\Mathew C\OneDrive\Documents\PPG"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "venv", "Lib", "site-packages"))

from main import run_pipeline, CONFIG
import file_manager

def run_automated_supervisor_test():
    print("Step 1: Copying user contest file from downloads under its original name...")
    src_file = r"D:\Downloads\June 2, 2026\detail.csv"
    dest_file = "data/detail.csv"
    
    if not os.path.exists(src_file):
        print(f"Error: Source file does not exist at {src_file}")
        return
        
    shutil.copy(src_file, dest_file)
    print(f"Copied {src_file} to {dest_file}")
    
    print("\nStep 2: Syncing with file manager and assigning 'Contest Data' tag...")
    file_manager.sync_metadata_with_disk()
    success, msg = file_manager.assign_tag_role("detail.csv", "Contest Data")
    print(f"Assign Tag Result: {success} - {msg}")
    
    print("\nStep 3: Inspecting contest file and generating matching voter file...")
    import contest_manager
    res_load = contest_manager.inspect_and_load_file("data/contest_data_input.csv")
    if res_load["status"] != "success":
        print(f"Error loading contest file: {res_load['message']}")
        return
        
    contest_df = res_load["df"]
    unique_precincts = contest_df["Precinct"].dropna().unique().tolist()
    print(f"Found {len(unique_precincts)} unique precincts in contest file.")
    
    # Generate mock voters to match the precinct names in this 2026 election
    random.seed(42)
    voter_rows = []
    for p in unique_precincts:
        for _ in range(50):
            party = random.choice(["DEM", "REP", "NPP", "OTHER"])
            voted_24 = random.choice(["1", ""])
            voted_22 = random.choice(["1", ""])
            voter_rows.append({
                "PrecinctName": p,
                "Party": party,
                "General24": voted_24,
                "General22": voted_22
            })
            
    voter_df = pd.DataFrame(voter_rows)
    voter_df.to_csv("data/voter_file.csv", index=False)
    print("Saved matching data/voter_file.csv.")
    
    print("\nStep 4: Writing precinct column mapping...")
    os.makedirs("outputs/contest_data_manager", exist_ok=True)
    with open("outputs/contest_data_manager/contest_precinct_col.txt", "w", encoding="utf-8") as f:
        f.write("Precinct")
        
    print("\nStep 5: Writing contest classification configuration...")
    # Classifying it as a Candidate type with:
    # Favorable = MELANIE BAGBY - Total Votes
    # Opposition = TOM SCHWEDHELM - Total Votes
    config_data = [
        {
            "name": "Supervisor D4 Primary",
            "year": 2026,
            "election_type": "Primary",
            "contest_type": "Candidate",
            "influence_component": "Support Score",
            "weight": 0.5,
            "favorable_col": "MELANIE BAGBY - Total Votes",
            "opposition_col": "TOM SCHWEDHELM - Total Votes"
        }
    ]
    
    with open("outputs/contest_data_manager/contest_classification_config.json", "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    print("Saved classification config.")
    
    print("\nStep 6: Executing Pipeline...")
    result = run_pipeline(
        weights={"turnout_gap": 0.45, "competitive_index": 0.35, "density": 0.20},
        target_params={"ad": None, "sd": None, "city": None},
        allow_mock=False,
        derive_sonoma_sd=True,
        contest_file_path="data/contest_data_input.csv",
        contest_prec_col="Precinct",
        contest_influence_weight=0.30,
        allow_low_coverage_contest=True
    )
    
    if result.get("status") == "success":
        print("\n✅ PIPELINE RUN COMPLETED SUCCESSFULLY!")
        
        top_df = result["top_precincts"]
        print(f"Total Precincts Scored: {len(top_df)}")
        
        # Display top 15 precincts showing Melanie Bagby support and rank changes
        cols_to_print = ["PrecinctName", "Base_Rank", "Final_Rank", "Rank_Change", "Base_Priority_Score", "Contest_Enrichment_Score", "Final_Priority_Score"]
        available_print_cols = [c for c in cols_to_print if c in top_df.columns]
        print("\nTop 15 Priority Precincts:")
        print(top_df.sort_values("Final_Priority_Score", ascending=False).head(15)[available_print_cols].to_string(index=False))
        
    else:
        print(f"\n❌ Pipeline failed: {result.get('message') or result.get('error')}")

if __name__ == "__main__":
    run_automated_supervisor_test()
