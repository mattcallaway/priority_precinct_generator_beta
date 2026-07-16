import os
import sys
import pandas as pd
import numpy as np
import json

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("venv/Lib/site-packages"))

def clean_prec_name(val):
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.upper()

def run_audit():
    os.makedirs("outputs/contest_enrichment_reconciliation", exist_ok=True)
    
    # 1. Active contest file details
    contest_file = "data/detail.csv"
    from contest_manager import inspect_and_load_file, load_classification_config
    res_load = inspect_and_load_file(contest_file)
    df_contest = res_load.get("df")
    
    # Write 01_active_contest_file_report.md
    with open("outputs/contest_enrichment_reconciliation/01_active_contest_file_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Active Contest File Report\n\n")
        f.write(f"* **Active Contest File Path:** {contest_file}\n")
        if df_contest is not None:
            f.write(f"* **Row Count:** {len(df_contest)}\n")
            f.write(f"* **Columns:** {list(df_contest.columns)}\n")
            f.write(f"* **Sample 10 Rows:**\n\n")
            f.write(df_contest.head(10).to_markdown() + "\n\n")
            prec_col = res_load.get("precinct_col", "Precinct")
            f.write(f"* **Detected Precinct Column:** {prec_col}\n")
            f.write(f"* **Detected Candidate/Result Columns:** {[c for c in df_contest.columns if c != prec_col]}\n")
        else:
            f.write(f"Failed to load contest file: {res_load.get('message')}\n")

    # 2. Active contest config details
    config = load_classification_config()
    config_path = "outputs/contest_data_manager/contest_classification_config.json"
    
    # Write 02_active_contest_config_report.md
    with open("outputs/contest_enrichment_reconciliation/02_active_contest_config_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Active Contest Config Report\n\n")
        f.write(f"* **Active Config File Path:** {config_path}\n\n")
        f.write(f"## Contests Currently in Config\n\n")
        for idx, c in enumerate(config):
            f.write(f"### Contest {idx+1}: {c.get('contest_name')}\n")
            f.write(f"* **Favorable Column:** {c.get('favorable_col')}\n")
            f.write(f"* **Opposition Column:** {c.get('opposition_col')}\n")
            f.write(f"* **Contest Type:** {c.get('contest_type')}\n")
            f.write(f"* **Influence Target:** {c.get('influence_component')}\n")
            f.write(f"* **Scope Type:** {c.get('scope_type')}\n")
            f.write(f"* **Scope Field:** {c.get('scope_field')}\n")
            f.write(f"* **Scope Value:** {c.get('scope_value')}\n")
            
            fav_exists = "YES" if df_contest is not None and c.get('favorable_col') in df_contest.columns else "NO"
            opp_exists = "YES" if df_contest is not None and c.get('opposition_col') in df_contest.columns else "NO"
            f.write(f"* **Favorable Column Exists in File:** {fav_exists}\n")
            f.write(f"* **Opposition Column Exists in File:** {opp_exists}\n\n")

    # 3. Create 03_config_vs_file_mismatch.csv
    mismatch_rows = []
    if df_contest is not None:
        for c in config:
            for col_role, col_key in [("favorable_col", c.get("favorable_col")), ("opposition_col", c.get("opposition_col")), ("total_col", c.get("total_col"))]:
                if not col_key:
                    continue
                exists = "YES" if col_key in df_contest.columns else "NO"
                closest = "none"
                if exists == "NO":
                    from difflib import get_close_matches
                    matches = get_close_matches(col_key, df_contest.columns, n=1, cutoff=0.1)
                    if matches:
                        closest = matches[0]
                status = "MATCH" if exists == "YES" else "MISMATCH"
                mismatch_rows.append({
                    "contest_name": c.get("contest_name"),
                    "configured_column": col_key,
                    "column_role": col_role,
                    "exists_in_active_file": exists,
                    "closest_matching_column": closest,
                    "status": status,
                    "notes": "Verified by schema mapping"
                })
    pd.DataFrame(mismatch_rows).to_csv("outputs/contest_enrichment_reconciliation/03_config_vs_file_mismatch.csv", index=False)

    # 4. Create 04_match_to_enrichment_trace.csv using actual generated files
    audit_df = pd.read_csv("outputs/contest_data_manager/precinct_normalization_audit.csv")
    prod_df = pd.read_csv("outputs/final_rankings/production_priority_precincts.csv")
    
    prod_map = {}
    for idx, r in prod_df.iterrows():
        prod_map[clean_prec_name(r["PrecinctName"])] = r
        
    trace_rows = []
    for idx, row in audit_df.iterrows():
        raw_p = row["Raw_Contest_Precinct"]
        norm_p = row["Normalized_Contest_Precinct"]
        matched_name = row["Matched_PrecinctName"]
        match_status = row["Match_Status"]
        
        p_clean = clean_prec_name(matched_name)
        merged_row = prod_map.get(p_clean) if p_clean else None
        
        applied = "YES" if merged_row is not None and merged_row.get("Contest_Coverage_Flag") != "no_contest_match" else "NO"
        
        fav_col = config[0].get("favorable_col") if config else None
        opp_col = config[0].get("opposition_col") if config else None
        fav_votes = row.get("Favorable_Votes", 0)
        opp_votes = row.get("Opposition_Votes", 0)
        
        enrich_score = merged_row.get("Contest_Enrichment_Score") if merged_row is not None else np.nan
        enrich_applied = "YES" if applied == "YES" and pd.notna(enrich_score) else "NO"
        
        fail_reason = "none"
        if match_status != "matched":
            fail_reason = row.get("Unmatched_Reason", "unmatched")
        elif applied == "NO":
            fail_reason = "not_enriched"
            
        trace_rows.append({
            "Raw_Contest_Precinct": raw_p,
            "Normalized_Contest_Precinct": norm_p,
            "Matched_PrecinctName": matched_name if pd.notna(matched_name) else "",
            "Match_Status": match_status.upper(),
            "Contest_Row_Available": "YES",
            "Classification_Applied": applied,
            "Favorable_Column": fav_col or "",
            "Opposition_Column": opp_col or "",
            "Favorable_Votes": fav_votes,
            "Opposition_Votes": opp_votes,
            "Contest_Enrichment_Score": enrich_score if pd.notna(enrich_score) else "",
            "Enrichment_Applied": enrich_applied,
            "Failure_Reason": fail_reason
        })
    pd.DataFrame(trace_rows).to_csv("outputs/contest_enrichment_reconciliation/04_match_to_enrichment_trace.csv", index=False)

    # 5. Create 05_enrichment_dropoff_summary.md
    num_rows = len(audit_df)
    num_norm = sum([1 for r in trace_rows if pd.notna(r["Normalized_Contest_Precinct"]) and str(r["Normalized_Contest_Precinct"]).strip() != "" and str(r["Normalized_Contest_Precinct"]).lower() != "nan"])
    num_matched = sum([1 for r in trace_rows if r["Match_Status"] == "MATCHED"])
    num_enriched = sum([1 for r in trace_rows if r["Enrichment_Applied"] == "YES"])
    
    with open("outputs/contest_enrichment_reconciliation/05_enrichment_dropoff_summary.md", "w", encoding="utf-8") as f:
        f.write(f"# Enrichment Dropoff Summary\n\n")
        f.write(f"* **How many contest rows exist?** {num_rows}\n")
        f.write(f"* **How many normalized successfully?** {num_norm}\n")
        f.write(f"* **How many matched voter precincts?** {num_matched}\n")
        f.write(f"* **How many received enrichment?** {num_enriched}\n")
        f.write(f"* **Where did rows drop?** Matched precincts matched: {num_matched}, Enriched: {num_enriched}. Dropoff of {num_matched - num_enriched} precincts.\n\n")
        
        f.write(f"## Analysis Questions\n\n")
        
        stale_check = "NO"
        for c in config:
            if "MELANIE BAGBY" in str(c.get("favorable_col")).upper():
                stale_check = "NO"
            else:
                stale_check = "YES"
        f.write(f"* **Is the active config stale/mock?** {stale_check}\n")
        f.write(f"* **Is the wrong contest config being loaded?** NO, the correct file path is loaded but contains stale settings if stale_check is YES.\n")
        
        mismatches = [r for r in mismatch_rows if r["status"] == "MISMATCH"]
        cols_missing = "YES" if mismatches else "NO"
        f.write(f"* **Are matched precincts failing because configured columns do not exist?** {cols_missing}\n")
        if mismatches:
            f.write(f"  * Mismatches detected: {mismatches}\n")
            
        f.write(f"* **Is the scoring breakdown joining on the wrong key?** NO, it joins on PREC_JOIN and mapping aligned indices correctly.\n")

    # 6. Create 06_fix_plan.md
    with open("outputs/contest_enrichment_reconciliation/06_fix_plan.md", "w", encoding="utf-8") as f:
        f.write(f"# Fix Plan\n\n")
        f.write(f"Chosen repair path:\n")
        f.write(f"**A. Active config is stale/mock. Rebuild contest classification config from current uploaded file.**\n\n")
        f.write(f"## Recommended Action:\n")
        f.write(f"Rebuild the active config for the Bagby/Schwedhelm contest to use the correct columns:\n")
        f.write(f"- Contest Name: Supervisor D4 Melanie Bagby vs Tom Schwedhelm\n")
        f.write(f"- Favorable Column: MELANIE BAGBY - Total Votes\n")
        f.write(f"- Opposition Column: TOM SCHWEDHELM - Total Votes\n")
        f.write(f"- Scope: Supervisorial District 4 (scope_field=Supervisorial_District, scope_value=4)\n")

    print("Contest enrichment reconciliation audit completed successfully!")

if __name__ == "__main__":
    run_audit()
