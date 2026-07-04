import os
import json
import pandas as pd
import numpy as np

# Default Thresholds
MIN_CONTEST_MATCH_RATE = 80.0
OUTPUT_DIR = "outputs/contest_data_manager"

def clean_column_name(col):
    return str(col).strip()

def to_clean_str(val):
    if pd.isna(val) or val == '' or str(val).strip() == '' or str(val).lower() == 'nan':
        return 'Unmapped'
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except:
        return str(val).strip()

def clean_multi_level_headers(df):
    if df is None or df.empty or df.shape[0] < 2:
        return df
        
    # Check if row 1 of dataframe (which is row 2 of the file) contains 'precinct' or similar column headers
    row1_vals = df.iloc[1].astype(str).str.strip().str.lower().tolist()
    is_multi = False
    for val in row1_vals:
        if val in ['precinct', 'prec', 'pct', 'srprec', 'mprec']:
            is_multi = True
            break
            
    if is_multi:
        new_cols = []
        current_group = ""
        general_set = {'precinct', 'registered voters', 'total', 'voted', 'turnout', 'ballots cast'}
        
        row0_vals = df.iloc[0].tolist()
        row1_raw = df.iloc[1].tolist()
        
        for col_idx in range(df.shape[1]):
            val0 = row0_vals[col_idx]
            val1 = row1_raw[col_idx]
            
            val1_str = str(val1).strip() if pd.notna(val1) else f"Column_{col_idx}"
            val1_lower = val1_str.lower()
            
            if val1_lower in general_set:
                current_group = ""
            elif pd.notna(val0) and str(val0).strip() != "":
                current_group = str(val0).strip()
                
            if current_group:
                new_cols.append(f"{current_group} - {val1_str}")
            else:
                new_cols.append(val1_str)
                
        df.columns = new_cols
        df = df.iloc[2:].reset_index(drop=True)
        
    return df

def inspect_and_load_file(file_path, sheet_name=None):
    """
    Ingests and inspects the upload file.
    Detects HTML disguised as XLS, CSV, TSV, and Excel files.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    # 1. Read first 2000 bytes to check if it's HTML disguised as XLS
    try:
        with open(file_path, "rb") as f:
            head_bytes = f.read(2000)
        head_str = head_bytes.decode("utf-8", errors="ignore").lower()
        if "<html" in head_str or "<table" in head_str:
            return {
                "status": "error",
                "error_type": "html_disguised_xls",
                "message": "The file appears to be an HTML document disguised as an Excel (.xls) file, which is unsupported."
            }
    except Exception as e:
        # If binary read fails, pass through to standard parsers
        pass

    # 2. Determine and parse by extension
    ext = os.path.splitext(file_path)[1].lower()
    df = None
    sheet_names = ["Default"]

    try:
        if ext == ".csv":
            df = pd.read_csv(file_path)
            file_type = "CSV"
        elif ext == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
            file_type = "TSV"
        elif ext in [".xlsx", ".xls"]:
            with pd.ExcelFile(file_path) as xl:
                sheet_names = xl.sheet_names
                selected_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
                df = xl.parse(selected_sheet)
            file_type = f"Excel ({ext})"
        else:
            return {
                "status": "error",
                "message": f"Unsupported file extension: {ext}. Only .csv, .tsv, .xls, and .xlsx are supported."
            }
    except Exception as e:
        return {"status": "error", "message": f"Failed to parse file: {str(e)}"}

    df = clean_multi_level_headers(df)

    return {
        "status": "success",
        "file_type": file_type,
        "sheet_names": sheet_names,
        "df": df
    }

def generate_file_inventory(file_path, sheet_name=None, output_dir=OUTPUT_DIR):
    """
    Generates a diagnostics preview inventory text file for the uploaded file.
    """
    os.makedirs(output_dir, exist_ok=True)
    res = inspect_and_load_file(file_path, sheet_name=sheet_name)
    if res["status"] != "success":
        return res

    df = res["df"]
    file_type = res["file_type"]
    sheet_names = res["sheet_names"]
    active_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]

    # Detect precinct-like columns (contains prec, pct, or district keywords)
    prec_cols = []
    contest_cols = []
    for col in df.columns:
        c_low = str(col).lower()
        if any(x in c_low for x in ["precinct", "prec", "pct", "srprec", "mprec"]):
            prec_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            contest_cols.append(col)

    row_count, col_count = df.shape

    inventory_path = os.path.join(output_dir, "contest_file_inventory.txt")
    with open(inventory_path, "w", encoding="utf-8") as f:
        f.write("CONTEST FILE INVENTORY REPORT\n")
        f.write("============================\n\n")
        f.write(f"File Path: {file_path}\n")
        f.write(f"Detected Format: {file_type}\n")
        f.write(f"Available Sheets: {', '.join(sheet_names)}\n")
        f.write(f"Active Sheet Analyzed: {active_sheet}\n")
        f.write(f"Total Rows: {row_count}\n")
        f.write(f"Total Columns: {col_count}\n")
        f.write(f"Likely Header Row: Row 1 (Index 0)\n\n")
        
        f.write("Precinct-like Columns Detected:\n")
        for pc in prec_cols:
            f.write(f"- {pc}\n")
        if not prec_cols:
            f.write("- None\n")
            
        f.write("\nNumeric/Contest-like Columns Detected:\n")
        for cc in contest_cols[:30]:  # Cap at 30 for viewability
            f.write(f"- {cc}\n")
        if len(contest_cols) > 30:
            f.write(f"- ... and {len(contest_cols) - 30} more numeric columns.\n")
            
        f.write("\nSample Rows Preview (First 5):\n")
        f.write(df.head(5).to_string())

    return {
        "status": "success",
        "inventory_path": inventory_path,
        "row_count": row_count,
        "col_count": col_count,
        "precinct_cols": prec_cols,
        "contest_cols": contest_cols,
        "df": df
    }

def generate_precinct_match_report(contest_df, contest_precinct_col, voter_precincts, output_dir=OUTPUT_DIR):
    """
    Compares the contest file's precinct column against voter-file PrecinctNames.
    Generates outputs/contest_data_manager/contest_precinct_match_report.csv
    """
    os.makedirs(output_dir, exist_ok=True)
    if contest_precinct_col not in contest_df.columns:
        return {"status": "error", "message": f"Selected precinct column '{contest_precinct_col}' not found in file."}

    # Get unique normalized precinct keys
    contest_keys = contest_df[contest_precinct_col].dropna().apply(to_clean_str).astype(str).str.strip().str.upper().unique().tolist()
    voter_keys = [to_clean_str(x).upper() for x in voter_precincts]

    contest_set = set(contest_keys)
    voter_set = set(voter_keys)

    matches = contest_set.intersection(voter_set)
    unmatched_contest = contest_set - voter_set
    unmatched_voter = voter_set - contest_set

    match_rate = (len(matches) / len(contest_set) * 100.0) if len(contest_set) > 0 else 0.0

    # Write report CSV
    report_rows = []
    for k in contest_keys:
        report_rows.append({
            "Contest_Precinct_Raw": k,
            "Is_Matched": "Yes" if k in voter_set else "No",
            "Matched_Voter_Precinct_Key": k if k in voter_set else ""
        })
    
    report_df = pd.DataFrame(report_rows)
    report_path = os.path.join(output_dir, "contest_precinct_match_report.csv")
    report_df.to_csv(report_path, index=False)

    return {
        "status": "success",
        "match_rate": match_rate,
        "exact_match_count": len(matches),
        "total_contest_precincts": len(contest_set),
        "total_voter_precincts": len(voter_set),
        "unmatched_contest_count": len(unmatched_contest),
        "unmatched_voter_count": len(unmatched_voter),
        "report_path": report_path
    }

def save_classification_config(config_list, output_dir=OUTPUT_DIR):
    """
    Saves the user-defined contest metadata and classification rules.
    """
    os.makedirs(output_dir, exist_ok=True)
    config_path = os.path.join(output_dir, "contest_classification_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_list, f, indent=2)
    return config_path

def load_classification_config(output_dir=OUTPUT_DIR):
    config_path = os.path.join(output_dir, "contest_classification_config.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_enrichment_calculations(base_scored_df, contest_df, contest_prec_col, config, influence_weight=0.20, output_dir=OUTPUT_DIR):
    """
    Performs precinct-level calculations on the classified contests,
    aggregates support, persuasion, turnout, and issue-alignment enrichment scores,
    and returns a combined dataframe along with generating diagnostic outputs.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Standardize join key on both datasets
    df_base = base_scored_df.copy()
    df_base['SRPREC_JOIN'] = df_base['SRPREC'].apply(to_clean_str).astype(str).str.strip().str.upper()
    
    df_contest = contest_df.copy()
    df_contest['PREC_JOIN'] = df_contest[contest_prec_col].apply(to_clean_str).astype(str).str.strip().str.upper()
    
    # Store intermediate calculated columns here
    df_calc = pd.DataFrame({'PREC_JOIN': df_contest['PREC_JOIN'].unique()})
    
    # Track scoring variables
    components = {
        "Support": [],           # List of (weight, score_col)
        "Persuasion": [],
        "Turnout": [],
        "Issue_Alignment": []
    }
    
    contest_sources = []
    
    for idx, rule in enumerate(config):
        c_name = rule.get("name", f"Contest_{idx}")
        c_type = rule.get("contest_type")
        influence = rule.get("influence_component")
        weight = float(rule.get("weight", 0.5))
        
        calc_col = f"Calc_{idx}_{c_name.replace(' ', '_')}"
        df_calc[calc_col] = np.nan
        
        try:
            if c_type == "Candidate":
                fav_col = rule.get("favorable_col")
                opp_col = rule.get("opposition_col")
                if fav_col in df_contest.columns and opp_col in df_contest.columns:
                    fav_val = pd.to_numeric(df_contest[fav_col], errors='coerce').fillna(0)
                    opp_val = pd.to_numeric(df_contest[opp_col], errors='coerce').fillna(0)
                    tot = fav_val + opp_val
                    # Competitiveness / Support Margin calculations
                    df_calc[calc_col] = (fav_val / tot.replace(0, np.nan)).fillna(0)
                    
            elif c_type == "Initiative / ballot measure":
                fav_col = rule.get("favorable_col")
                tot_col = rule.get("total_col")
                if fav_col in df_contest.columns and tot_col in df_contest.columns:
                    fav_val = pd.to_numeric(df_contest[fav_col], errors='coerce').fillna(0)
                    tot_val = pd.to_numeric(df_contest[tot_col], errors='coerce').fillna(0)
                    df_calc[calc_col] = (fav_val / tot_val.replace(0, np.nan)).fillna(0)
                    
            elif c_type == "Turnout":
                ballots_col = rule.get("ballots_col")
                reg_col = rule.get("reg_col")
                if ballots_col in df_contest.columns and reg_col in df_contest.columns:
                    ballots = pd.to_numeric(df_contest[ballots_col], errors='coerce').fillna(0)
                    reg = pd.to_numeric(df_contest[reg_col], errors='coerce').fillna(0)
                    df_calc[calc_col] = (ballots / reg.replace(0, np.nan)).fillna(0)
                    
            elif c_type == "Party baseline":
                fav_col = rule.get("favorable_col")
                tot_col = rule.get("total_col")
                if fav_col in df_contest.columns and tot_col in df_contest.columns:
                    fav_val = pd.to_numeric(df_contest[fav_col], errors='coerce').fillna(0)
                    tot_val = pd.to_numeric(df_contest[tot_col], errors='coerce').fillna(0)
                    df_calc[calc_col] = (fav_val / tot_val.replace(0, np.nan)).fillna(0)
            
            # Map calculated column to target component list if mapped
            mapped_comp = None
            if influence == "Support Score":
                mapped_comp = "Support"
            elif influence == "Persuasion Score":
                mapped_comp = "Persuasion"
            elif influence == "Turnout Score":
                mapped_comp = "Turnout"
            elif influence == "Issue Alignment Score":
                mapped_comp = "Issue_Alignment"
                
            if mapped_comp:
                components[mapped_comp].append((weight, calc_col))
                contest_sources.append(f"{c_name} (Weight: {weight})")
                
        except Exception as e:
            # Ignore and leave column as NaN if calculation fails
            pass

    # Merge base precinct records with intermediate contest calculations
    df_merged = pd.merge(df_base, df_calc, left_on='SRPREC_JOIN', right_on='PREC_JOIN', how='left')
    
    # Calculate enrichment scores per component
    for comp_name, rules_list in components.items():
        score_col = f"Contest_{comp_name}_Score"
        df_merged[score_col] = np.nan
        
        if rules_list:
            # Weighted average calculation across active columns
            w_sum = pd.Series(0.0, index=df_merged.index)
            val_sum = pd.Series(0.0, index=df_merged.index)
            
            for w, c_col in rules_list:
                mask = df_merged[c_col].notna()
                w_sum.loc[mask] += w
                val_sum.loc[mask] += w * df_merged.loc[mask, c_col]
                
            df_merged[score_col] = (val_sum / w_sum.replace(0, np.nan))
            
    # Calculate Coverage rate and Overall Contest Confidence
    # Contest Confidence = total weights matched divided by total weights classified
    total_classified_weight = sum([w for comp in components.values() for w, _ in comp])
    
    df_merged["Contest_Confidence"] = 0.0
    df_merged["Contest_Coverage_Flag"] = "No Coverage"
    
    if total_classified_weight > 0:
        w_sum_overall = pd.Series(0.0, index=df_merged.index)
        for comp in components.values():
            for w, c_col in comp:
                mask = df_merged[c_col].notna()
                w_sum_overall.loc[mask] += w
        
        df_merged["Contest_Confidence"] = w_sum_overall / total_classified_weight
        df_merged.loc[df_merged["Contest_Confidence"] > 0, "Contest_Coverage_Flag"] = "Partial Coverage"
        df_merged.loc[df_merged["Contest_Confidence"] >= 0.99, "Contest_Coverage_Flag"] = "Full Coverage"

    # Compute Contest_Enrichment_Score as the average of non-null target components
    enrich_cols = [f"Contest_{comp_name}_Score" for comp_name in components.keys()]
    df_merged["Contest_Enrichment_Score"] = df_merged[enrich_cols].mean(axis=1)
    
    # Calculate Final Priority Score combining Base + Enrichment
    # Final = (1 - influence) * Base + influence * Enrichment (or Base if Enrichment is NaN)
    df_merged["Base_Priority_Score"] = df_merged["Priority_Score"]
    
    has_enrich = df_merged["Contest_Enrichment_Score"].notna()
    df_merged["Final_Priority_Score"] = df_merged["Base_Priority_Score"]
    df_merged.loc[has_enrich, "Final_Priority_Score"] = (
        (1.0 - influence_weight) * df_merged.loc[has_enrich, "Base_Priority_Score"] +
        influence_weight * df_merged.loc[has_enrich, "Contest_Enrichment_Score"]
    )
    
    df_merged["Contest_Source_Summary"] = ", ".join(contest_sources) if contest_sources else "None"
    
    # Calculate Base Rank and Final Rank
    df_merged["Base_Rank"] = df_merged["Base_Priority_Score"].rank(ascending=False, method='min').astype(int)
    df_merged["Final_Rank"] = df_merged["Final_Priority_Score"].rank(ascending=False, method='min').astype(int)
    df_merged["Rank_Change"] = df_merged["Base_Rank"] - df_merged["Final_Rank"]
    
    # Clean temporary intermediate calculation columns
    drop_cols = [c for c in df_merged.columns if c.startswith("Calc_") or c in ['SRPREC_JOIN', 'PREC_JOIN']]
    df_final = df_merged.drop(columns=drop_cols, errors='ignore')
    
    # Save diagnostics
    save_diagnostics(df_final, config, base_scored_df, df_contest, contest_prec_col, output_dir)
    
    return df_final

def save_diagnostics(df_final, config, base_scored_df, contest_df, contest_prec_col, output_dir):
    """
    Generates all diagnostic report files in outputs/contest_data_manager/
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. contest_scoring_breakdown.csv
    breakdown_cols = [
        "SRPREC", "Base_Priority_Score", "Contest_Enrichment_Score", "Final_Priority_Score",
        "Contest_Support_Score", "Contest_Persuasion_Score", "Contest_Turnout_Score",
        "Contest_Issue_Alignment_Score", "Contest_Confidence"
    ]
    df_final[breakdown_cols].to_csv(os.path.join(output_dir, "contest_scoring_breakdown.csv"), index=False)
    
    # 2. contest_coverage_report.csv
    cov_cols = ["SRPREC", "Contest_Confidence", "Contest_Coverage_Flag", "Contest_Source_Summary"]
    df_final[cov_cols].to_csv(os.path.join(output_dir, "contest_coverage_report.csv"), index=False)
    
    # 3. contest_rank_shift_report.csv
    shift_cols = ["SRPREC", "Base_Rank", "Final_Rank", "Rank_Change", "Base_Priority_Score", "Final_Priority_Score", "Contest_Source_Summary"]
    df_final[shift_cols].to_csv(os.path.join(output_dir, "contest_rank_shift_report.csv"), index=False)
    
    # 4. contest_enrichment_summary.md
    summary_path = os.path.join(output_dir, "contest_enrichment_summary.md")
    
    total_precincts = len(df_final)
    covered_precincts = len(df_final[df_final["Contest_Confidence"] > 0])
    coverage_rate_overall = (covered_precincts / total_precincts * 100.0) if total_precincts > 0 else 0.0
    
    rank_shifts = df_final[df_final["Rank_Change"] != 0]
    avg_shift = rank_shifts["Rank_Change"].abs().mean() if len(rank_shifts) > 0 else 0.0
    max_shift = rank_shifts["Rank_Change"].abs().max() if len(rank_shifts) > 0 else 0
    
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Contest Enrichment Summary\n\n")
        f.write("## Execution Status\n")
        f.write(f"- **Total Precincts Scored:** {total_precincts}\n")
        f.write(f"- **Precincts with Contest Data:** {covered_precincts} ({coverage_rate_overall:.1f}% coverage)\n")
        f.write(f"- **Contests Used:** {len(config)}\n\n")
        
        f.write("## Ranking Shift Analysis\n")
        f.write(f"- **Precincts with Rank Shifts:** {len(rank_shifts)} / {total_precincts}\n")
        f.write(f"- **Average Rank Shift magnitude:** {avg_shift:.1f} positions\n")
        f.write(f"- **Maximum Rank Shift magnitude:** {max_shift} positions\n\n")
        
        f.write("## Contests Used in Scoring Model\n")
        for idx, rule in enumerate(config):
            f.write(f"- **Name:** {rule.get('name')} | **Type:** {rule.get('contest_type')} | **Weight:** {rule.get('weight')} | **Target:** {rule.get('influence_component')}\n")
            
        f.write("\n## Trustworthiness & Guardrails Status\n")
        if coverage_rate_overall < 80.0:
            f.write("> [!WARNING]\n")
            f.write(f"> **Low Coverage Warning:** Contest data maps to only {coverage_rate_overall:.1f}% of precincts. Model rankings may be skewed for missing precincts.\n\n")
        else:
            f.write("> [!NOTE]\n")
            f.write("> **Coverage Standard Met:** Contest data coverage is high and trustworthy across the target county.\n\n")
