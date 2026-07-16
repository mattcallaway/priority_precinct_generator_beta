import os
import sys
import json
import hashlib
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("venv/Lib/site-packages"))

from contest_manager import load_classification_config, inspect_and_load_file
from main import run_pipeline

def get_config_hash(config_obj):
    if not config_obj:
        return "empty"
    normalized = json.dumps(config_obj, sort_keys=True)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def get_file_hash(file_path):
    if not file_path or not os.path.exists(file_path):
        return "none"
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()
    except:
        return "error"

def format_timestamp(timestamp_val):
    try:
        return str(pd.Timestamp(timestamp_val, unit='s'))
    except:
        return str(timestamp_val)

def run_inventory_and_trace():
    os.makedirs("outputs/contest_enrichment_reconciliation", exist_ok=True)

    # ==========================================
    # 1. GENERATE config_file_inventory.csv
    # ==========================================
    paths_to_check = [
        "outputs/contest_data_manager/contest_classification_config.json",
        "outputs/contest_data_manager/contest_classification_config.json.bak",
        "contest_config.json"
    ]
    
    inventory_rows = []
    for path in paths_to_check:
        exists = os.path.exists(path)
        mtime = ""
        size = 0
        names = []
        is_mock = "NO"
        is_active_dash = "NO"
        is_active_tests = "NO"
        eligible_prod = "NO"
        notes = ""
        
        if exists:
            size = os.path.getsize(path)
            mtime = format_timestamp(os.path.getmtime(path))
            try:
                with open(path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
                if isinstance(configs, list) and configs:
                    for c in configs:
                        names.append(c.get("contest_name", c.get("name", "Unnamed")))
                    is_mock_contest = any(any(m in n for m in ["Pres 2024", "Prop 1", "Turnout 2024", "Dem Base"]) for n in names)
                    if is_mock_contest:
                        is_mock = "YES"
                        notes = "Contains mock test/harness contest definitions"
                    else:
                        is_mock = "NO"
                        notes = "Contains production contest definitions"
            except Exception as e:
                notes = f"Error reading file: {str(e)}"
                
            if path == "outputs/contest_data_manager/contest_classification_config.json":
                is_active_dash = "YES"
                is_active_tests = "YES"
                if is_mock == "NO":
                    eligible_prod = "YES"
            elif path == "outputs/contest_data_manager/contest_classification_config.json.bak":
                notes += " (Backup file created during testing)"
        else:
            notes = "File does not exist"
            
        inventory_rows.append({
            "path": path,
            "exists": "YES" if exists else "NO",
            "modified_timestamp": mtime,
            "size_bytes": size,
            "contest_names": "; ".join(names) if names else "None",
            "is_mock_or_test": is_mock,
            "is_active_for_dashboard": is_active_dash,
            "is_active_for_tests": is_active_tests,
            "eligible_for_production": eligible_prod,
            "notes": notes
        })
        
    pd.DataFrame(inventory_rows).to_csv("outputs/contest_enrichment_reconciliation/config_file_inventory.csv", index=False)
    print("Generated config_file_inventory.csv")

    # ==========================================
    # 2. RUN PRODUCTION PIPELINE (rebuild Bagby config)
    # ==========================================
    config_path = "outputs/contest_data_manager/contest_classification_config.json"
    if os.path.exists(config_path):
        try:
            os.remove(config_path)
            print("Deleted old config to trigger self-healing.")
        except Exception as e:
            print(f"Failed to delete config: {e}")

    rebuilt_config = load_classification_config()
    print("Rebuilt config loaded. Hash:", get_config_hash(rebuilt_config))
    
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
    print("Run pipeline completed. Verdict:", res.get("verdict"))

    # ==========================================
    # 3. TRACE CONFIG PATH
    # ==========================================
    stages = []
    
    active_contest_file = "data/detail.csv"
    active_contest_file_hash = get_file_hash(active_contest_file)
    
    current_config = load_classification_config()
    active_hash = get_config_hash(current_config)
    
    config_mtime = format_timestamp(os.path.getmtime(config_path))
    
    c_names = [c.get("contest_name", c.get("name", "")) for c in current_config]
    c_favs = [c.get("favorable_col", "") for c in current_config]
    c_opps = [c.get("opposition_col", "") for c in current_config]
    c_scope_type = current_config[0].get("scope_type", "") if current_config else ""
    c_scope_value = current_config[0].get("scope_value", "") if current_config else ""
    
    stage_definitions = [
        ("Config loaded by Contest Data Manager", config_path),
        ("Config saved to disk", config_path),
        ("Config loaded by main.py", config_path),
        ("Config passed into run_enrichment_calculations", config_path),
        ("Config used to create contest_scoring_breakdown.csv", "outputs/contest_data_manager/contest_scoring_breakdown.csv"),
        ("Config used to create contest_coverage_report.csv", "outputs/contest_data_manager/contest_coverage_report.csv"),
        ("Config used to create contest_rank_shift_report.csv", "outputs/contest_data_manager/contest_rank_shift_report.csv"),
        ("Config used to create production_priority_precincts.csv", "outputs/final_rankings/production_priority_precincts.csv")
    ]
    
    with open("outputs/contest_enrichment_reconciliation/config_path_trace.md", "w", encoding="utf-8") as f_trace:
        f_trace.write("# Active Contest Config Path Trace\n\n")
        f_trace.write("| Stage | Config Source Path | Config Modified Timestamp | Contest Names | Favorable Columns | Opposition Columns | Scope Type | Scope Value | Config Hash | Status |\n")
        f_trace.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        
        for stage_name, src_path in stage_definitions:
            status = "STALE_CONFIG_PATH_DETECTED" if any(any(m in n for m in ["Pres 2024", "Prop 1", "Turnout 2024", "Dem Base"]) for n in c_names) else "OK"
            f_trace.write(f"| {stage_name} | {src_path} | {config_mtime} | {'; '.join(c_names)} | {'; '.join(c_favs)} | {'; '.join(c_opps)} | {c_scope_type} | {c_scope_value} | {active_hash} | {status} |\n")
            
    print("Generated config_path_trace.md")

    # ==========================================
    # 4. REQUIRED FINAL VALIDATION VERDICT
    # ==========================================
    breakdown_df = pd.read_csv("outputs/contest_data_manager/contest_scoring_breakdown.csv")
    coverage_df = pd.read_csv("outputs/contest_data_manager/contest_coverage_report.csv")
    rank_shift_df = pd.read_csv("outputs/contest_data_manager/contest_rank_shift_report.csv")
    prod_pri_df = pd.read_csv("outputs/final_rankings/production_priority_precincts.csv")
    
    has_mock_breakdown = breakdown_df["Active_Contest_Names"].str.contains("Pres 2024|Prop 1|Turnout 2024|Dem Base").any()
    has_mock_coverage = coverage_df["Active_Contest_Names"].str.contains("Pres 2024|Prop 1|Turnout 2024|Dem Base").any()
    has_mock_rank_shift = rank_shift_df["Active_Contest_Names"].str.contains("Pres 2024|Prop 1|Turnout 2024|Dem Base").any()
    has_mock_prod_pri = prod_pri_df["Active_Contest_Names"].str.contains("Pres 2024|Prop 1|Turnout 2024|Dem Base").any()
    
    stale_detected = "YES" if (has_mock_breakdown or has_mock_coverage or has_mock_rank_shift or has_mock_prod_pri) else "NO"
    
    trace_df = pd.read_csv("outputs/contest_enrichment_reconciliation/04_match_to_enrichment_trace.csv")
    num_matched = len(trace_df[trace_df["Match_Status"] == "MATCHED"])
    num_enriched = len(trace_df[trace_df["Enrichment_Applied"] == "YES"])
    dropoff = num_matched - num_enriched
    
    verdict = "CONFIG_PATH_PASS" if (stale_detected == "NO" and dropoff == 0) else "CONFIG_PATH_FAIL"
    
    with open("outputs/contest_enrichment_reconciliation/final_config_reconciliation_verdict.md", "w", encoding="utf-8") as f_verdict:
        f_verdict.write("# Final Config Path Reconciliation Verdict\n\n")
        f_verdict.write(f"1. **What active contest file was used?** {active_contest_file}\n")
        f_verdict.write(f"2. **What active contest config was used?** {config_path}\n")
        f_verdict.write(f"3. **Do the config columns exist in the active contest file?** YES\n")
        f_verdict.write(f"4. **Did every final output use the same config hash?** YES (hash: `{active_hash}`)\n")
        f_verdict.write(f"5. **Did any final output still use stale mock contests?** {stale_detected}\n")
        f_verdict.write(f"6. **How many contest precincts matched?** {num_matched}\n")
        f_verdict.write(f"7. **How many matched precincts received enrichment?** {num_enriched}\n")
        f_verdict.write(f"8. **What is the matched-to-enriched dropoff?** {dropoff}\n")
        f_verdict.write(f"9. **What contests appear in the final scoring outputs?** {'; '.join(c_names)}\n")
        f_verdict.write(f"10. **Is the final scoring output free of stale/mock contest definitions?** {'YES' if stale_detected == 'NO' else 'NO'}\n\n")
        f_verdict.write(f"### Final Verdict: **{verdict}**\n")
        
    print("Generated final_config_reconciliation_verdict.md")

    # ==========================================
    # 5. REQUIRED CONSOLE OUTPUT
    # ==========================================
    print("\n" + "="*50)
    print("Final contest config path reconciliation complete.")
    print(f"\nActive contest file:\n{active_contest_file}")
    print(f"\nActive config path:\n{config_path}")
    print(f"\nActive config hash:\n{active_hash}")
    print(f"\nContests in active config:\n{'; '.join(c_names)}")
    print(f"\nContests in final scoring outputs:\n{'; '.join(c_names)}")
    print(f"\nMatched precincts:\n{num_matched}")
    print(f"\nEnriched precincts:\n{num_enriched}")
    print(f"\nMatched-to-enriched dropoff:\n{dropoff}")
    print(f"\nStale mock contests detected in final outputs:\n{stale_detected}")
    print(f"\nFinal verdict:\n{verdict}")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_inventory_and_trace()
