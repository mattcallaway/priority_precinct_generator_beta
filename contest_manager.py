import os
import sys
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
            val_str = str(int(f_val))
        else:
            val_str = str(f_val)
    except:
        val_str = str(val).strip()
        
    val_clean = val_str.lstrip('0')
    
    # Sonoma precinct crosswalk normalization (74X_YYY -> 4X0_YYY)
    if len(val_clean) == 6 and val_clean.startswith('74'):
        city = val_clean[2]
        seq = val_clean[3:]
        if len(seq) == 3:
            return f"4{city}0{seq}"
            
    return val_clean

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

def normalize_contest_precincts(contest_df, contest_prec_col, voter_precincts, county="Sonoma", output_dir=OUTPUT_DIR):
    """
    Normalizes contest precincts and outputs an audit log to outputs/contest_data_manager/precinct_normalization_audit.csv
    """
    voter_set_upper = {str(x).strip().upper() for x in voter_precincts}
    
    audit_rows = []
    normalized_list = []
    
    for idx, row in contest_df.iterrows():
        raw_prec = row[contest_prec_col]
        if pd.isna(raw_prec):
            normalized_list.append("Unmapped")
            continue
            
        raw_str = str(raw_prec).strip()
        
        # Convert float strings like '100.0' to '100'
        try:
            f_val = float(raw_str)
            if f_val.is_integer():
                raw_clean = str(int(f_val))
            else:
                raw_clean = str(f_val)
        except:
            raw_clean = raw_str
            
        val_clean = raw_clean.lstrip('0')
        if val_clean == '':
            val_clean = '0'
            
        rule_applied = "leading_zero_strip"
        norm_prec = val_clean
        
        # Determine rule
        if raw_clean.upper() in voter_set_upper:
            norm_prec = raw_clean
            rule_applied = "none_raw_match"
        elif val_clean.upper() in voter_set_upper:
            norm_prec = val_clean
            rule_applied = "leading_zero_strip"
        elif county == "Sonoma" and len(val_clean) == 6 and val_clean.startswith('74'):
            city = val_clean[2]
            seq = val_clean[3:]
            if len(seq) == 3:
                norm_prec = f"4{city}0{seq}"
                rule_applied = "sonoma_sov_precinct_format_rule"
        
        # Match status
        match_status = "unmatched"
        matched_name = ""
        norm_upper = norm_prec.upper()
        matched_orig = next((p for p in voter_precincts if str(p).strip().upper() == norm_upper), None)
        if matched_orig is not None:
            match_status = "matched"
            matched_name = str(matched_orig)
            
        audit_rows.append({
            "Raw_Contest_Precinct": raw_str,
            "Normalized_Contest_Precinct": norm_prec,
            "Normalization_Rule_Applied": rule_applied,
            "Matched_PrecinctName": matched_name,
            "Match_Status": match_status
        })
        normalized_list.append(norm_prec)
        
    audit_df = pd.DataFrame(audit_rows)
    os.makedirs(output_dir, exist_ok=True)
    audit_df.to_csv(os.path.join(output_dir, "precinct_normalization_audit.csv"), index=False)
    
    return normalized_list

def generate_precinct_match_report(contest_df, contest_precinct_col, voter_precincts, county="Sonoma", output_dir=OUTPUT_DIR):
    """
    Compares the contest file's precinct column against voter-file PrecinctNames.
    Generates outputs/contest_data_manager/contest_precinct_match_report.csv
    """
    os.makedirs(output_dir, exist_ok=True)
    if contest_precinct_col not in contest_df.columns:
        return {"status": "error", "message": f"Selected precinct column '{contest_precinct_col}' not found in file."}

    normalized_list = normalize_contest_precincts(contest_df, contest_precinct_col, voter_precincts, county=county, output_dir=output_dir)
    
    contest_keys = sorted(list(set(normalized_list)))
    voter_keys = [str(x).strip().upper() for x in voter_precincts]

    contest_set = set(contest_keys)
    voter_set = set(voter_keys)

    matches = contest_set.intersection(voter_set)
    unmatched_contest = contest_set - voter_set
    unmatched_voter = voter_set - contest_set

    match_rate = (len(matches) / len(contest_set) * 100.0) if len(contest_set) > 0 else 0.0

    report_rows = []
    audit_path = os.path.join(output_dir, "precinct_normalization_audit.csv")
    if os.path.exists(audit_path):
        audit_df = pd.read_csv(audit_path)
        for idx, row in audit_df.iterrows():
            report_rows.append({
                "Contest_Precinct_Raw": row["Raw_Contest_Precinct"],
                "Is_Matched": "Yes" if row["Match_Status"] == "matched" else "No",
                "Matched_Voter_Precinct_Key": row["Matched_PrecinctName"] if row["Match_Status"] == "matched" else ""
            })
    else:
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

FIXTURE_BLOCKED_WARNINGS = []

def is_test_mode_active():
    import sys
    import os
    env_mode = os.environ.get("PPG_RUN_MODE")
    if env_mode == "TEST_MODE":
        return True
    if env_mode == "PRODUCTION_MODE":
        return False
    if any("run_audit_tests" in arg or "test_streamlit_app" in arg for arg in sys.argv):
        return True
    return False

def is_fixture_path(path):
    if not path:
        return False
    normalized = str(path).replace("\\", "/").lower()
    return "tests/" in normalized or "tests/fixtures/" in normalized

def load_classification_config(output_dir=OUTPUT_DIR):
    global FIXTURE_BLOCKED_WARNINGS
    # Self-healing rebuild logic for Bagby file
    contest_file = "data/detail.csv"
    is_test_run = is_test_mode_active()
    if os.path.exists(contest_file) and not is_test_run:
        try:
            df_check = pd.read_csv(contest_file, nrows=3)
            has_bagby_cols = False
            for col in df_check.columns:
                if "MELANIE BAGBY" in str(col).upper():
                    has_bagby_cols = True
            for idx, r in df_check.iterrows():
                for val in r.values:
                    if "MELANIE BAGBY" in str(val).upper():
                        has_bagby_cols = True
            if has_bagby_cols:
                config_path_chk = os.path.join(output_dir, "contest_classification_config.json")
                is_stale = True
                if os.path.exists(config_path_chk):
                    with open(config_path_chk, "r", encoding="utf-8") as f_chk:
                        cur_configs = json.load(f_chk)
                    if cur_configs and isinstance(cur_configs, list) and isinstance(cur_configs[0], dict):
                        first_c = cur_configs[0]
                        if first_c.get("favorable_col") == "MELANIE BAGBY - Total Votes":
                            if first_c.get("scope_type") == "supervisorial_district" and str(first_c.get("scope_value")) == "4":
                                is_stale = False
                if is_stale:
                    new_config = [{
                        "contest_name": "Supervisor D4 Melanie Bagby vs Tom Schwedhelm",
                        "name": "Supervisor D4 Melanie Bagby vs Tom Schwedhelm",
                        "year": 2024,
                        "election_type": "Primary",
                        "contest_type": "Candidate",
                        "influence_component": "Support Score",
                        "weight": 0.5,
                        "favorable_col": "MELANIE BAGBY - Total Votes",
                        "opposition_col": "TOM SCHWEDHELM - Total Votes",
                        "scope_type": "supervisorial_district",
                        "scope_field": "Supervisorial_District",
                        "scope_value": "4",
                        "scope_confidence": "unconfirmed",
                        "scope_source": "self_healing_current_file",
                        "scope_user_confirmed": False,
                        "Config_Rebuild_Source": "self_healing_current_file",
                        "Production_Requires_User_Review": True
                    }]
                    with open(config_path_chk, "w", encoding="utf-8") as f_w:
                        json.dump(new_config, f_w, indent=2)
        except Exception as e:
            pass

    config_path = os.path.join(output_dir, "contest_classification_config.json")
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    if not isinstance(configs, list):
        return []
    
    updated_configs = []
    for c in configs:
        if not isinstance(c, dict):
            continue
            
        src_file = c.get("source_file", "")
        if is_fixture_path(src_file) and not is_test_mode_active():
            if "fixture_contest_blocked_from_non_test_run" not in FIXTURE_BLOCKED_WARNINGS:
                FIXTURE_BLOCKED_WARNINGS.append("fixture_contest_blocked_from_non_test_run")
            continue
            
        # Standardize new contest_name key
        if "contest_name" not in c and "name" in c:
            c["contest_name"] = c["name"]
        elif "contest_name" not in c:
            c["contest_name"] = "Unnamed Contest"
            
        if "contest_type" not in c and "contest_type" in c:
            pass
        elif "contest_type" not in c:
            c["contest_type"] = "Other"
            
        if "election_type" not in c:
            c["election_type"] = "General"
            
        if "year" not in c:
            c["year"] = 2024
            
        # Scope Metadata defaults
        if "scope_type" not in c:
            c["scope_type"] = "countywide"
            c["scope_field"] = "County"
            c["scope_value"] = ""
            c["scope_confidence"] = "legacy"
            c["scope_source"] = "legacy"
            c["scope_user_confirmed"] = True
        else:
            c.setdefault("scope_field", "")
            c.setdefault("scope_value", "")
            c.setdefault("scope_confidence", "unconfirmed")
            c.setdefault("scope_source", "legacy")
            c.setdefault("scope_user_confirmed", False)
        
        updated_configs.append(c)
        
    return updated_configs

def add_config_provenance_columns(df, config, file_path, target_params=None, relationship=None):
    import hashlib
    import json
    
    config_path = "outputs/contest_data_manager/contest_classification_config.json"
    
    if config:
        normalized = json.dumps(config, sort_keys=True)
        config_hash = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    else:
        config_hash = "empty"
        
    c_names = []
    if config:
        for c in config:
            name = c.get("contest_name", c.get("name", "Unnamed Contest"))
            c_names.append(name)
    contest_names_str = "; ".join(c_names) if c_names else "None"
    
    act_file_path = file_path if file_path else "None"
    
    file_hash = "none"
    if file_path and os.path.exists(file_path):
        try:
            h = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
            file_hash = h.hexdigest()
        except:
            file_hash = "error"
            
    matches_file = "YES"
    if file_path and os.path.exists(file_path):
        try:
            res_l = inspect_and_load_file(file_path)
            if res_l["status"] == "success":
                file_cols = list(res_l["df"].columns)
                if config:
                    for c in config:
                        fav = c.get("favorable_col")
                        opp = c.get("opposition_col")
                        if fav and fav not in file_cols:
                            matches_file = "NO"
                        if opp and opp not in file_cols:
                            matches_file = "NO"
                else:
                    matches_file = "NO"
            else:
                matches_file = "NO"
        except:
            matches_file = "NO"
    else:
        matches_file = "NO"
        
    status = "unknown"
    if not config:
        status = "unknown"
    else:
        is_mock_contest = any(any(m in name for m in ["Pres 2024", "Prop 1", "Turnout 2024", "Dem Base"]) for name in c_names)
        
        is_bagby_file = False
        if file_path and os.path.exists(file_path):
            try:
                df_check = pd.read_csv(file_path, nrows=3)
                is_bagby_file = any("MELANIE BAGBY" in str(col).upper() for col in df_check.columns)
            except:
                pass
                
        if is_mock_contest and is_bagby_file:
            status = "stale_mock_config"
        elif is_mock_contest:
            status = "stale_mock_config"
        elif matches_file == "NO":
            status = "config_file_column_mismatch"
        elif relationship == "contest_narrower_than_selected_universe":
            status = "config_file_scope_mismatch"
        else:
            is_legacy = any(c.get("scope_source") == "legacy" for c in config)
            if is_legacy:
                status = "stale_legacy_config"
            else:
                status = "current_active_config"
                
    df["Active_Contest_Config_Path"] = config_path
    df["Active_Contest_Config_Hash"] = config_hash
    df["Active_Contest_Names"] = contest_names_str
    df["Active_Contest_File_Path"] = act_file_path
    df["Active_Contest_File_Hash"] = file_hash
    df["Contest_Config_Matches_Contest_File"] = matches_file
    df["Contest_Config_Status"] = status
    return df

def run_enrichment_calculations(base_scored_df, contest_df, contest_prec_col, config, influence_weight=0.20, county="Sonoma", output_dir=OUTPUT_DIR, contest_file_path=None, relationship=None):
    """
    Performs precinct-level calculations on the classified contests,
    aggregates support, persuasion, turnout, and issue-alignment enrichment scores,
    and returns a combined dataframe along with generating diagnostic outputs.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    df_base = base_scored_df.copy()
    
    crosswalk_path = "outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk.csv"
    
    reg_pdf = ""
    voting_pdf = ""
    if config:
        if isinstance(config, list) and len(config) > 0:
            first_rule = config[0]
            reg_pdf = first_rule.get("crosswalk_reg_to_voting_file", "")
            voting_pdf = first_rule.get("crosswalk_voting_to_reg_file", "")
        elif isinstance(config, dict):
            reg_pdf = config.get("crosswalk_reg_to_voting_file", "")
            voting_pdf = config.get("crosswalk_voting_to_reg_file", "")
    
    reg_pdf_path = ""
    if reg_pdf:
        if os.path.exists(reg_pdf):
            reg_pdf_path = reg_pdf
        elif os.path.exists(os.path.join("data", os.path.basename(reg_pdf))):
            reg_pdf_path = os.path.join("data", os.path.basename(reg_pdf))
            
    voting_pdf_path = ""
    if voting_pdf:
        if os.path.exists(voting_pdf):
            voting_pdf_path = voting_pdf
        elif os.path.exists(os.path.join("data", os.path.basename(voting_pdf))):
            voting_pdf_path = os.path.join("data", os.path.basename(voting_pdf))
            
    if not reg_pdf_path:
        default_reg = os.path.expanduser(r"~\Downloads\ewmr010_regabsvotpctxref_2026-06-02.pdf")
        if os.path.exists(default_reg):
            reg_pdf_path = default_reg
    if not voting_pdf_path:
        default_voting = os.path.expanduser(r"~\Downloads\ewmr008_votabsregpctxref_2026-06-02.pdf")
        if os.path.exists(default_voting):
            voting_pdf_path = default_voting
            
    # Resolve pre-parsed CSV files
    parsed_reg_csv = "outputs/precinct_crosswalk/parsed_regular_vbm_voting_xref.csv"
    parsed_vot_csv = "outputs/precinct_crosswalk/parsed_voting_vbm_regular_xref.csv"
    has_parsed_csvs = os.path.exists(parsed_reg_csv) and os.path.exists(parsed_vot_csv)
    
    if os.environ.get("DISABLE_SELF_HEALING_CROSSWALK") != "TRUE":
        rebuild = not os.path.exists(crosswalk_path)
        if not rebuild and reg_pdf_path and voting_pdf_path:
            try:
                out_mtime = os.path.getmtime(crosswalk_path)
                if os.path.getmtime(reg_pdf_path) > out_mtime or os.path.getmtime(voting_pdf_path) > out_mtime:
                    rebuild = True
            except:
                rebuild = True
                
        if rebuild and ((reg_pdf_path and voting_pdf_path) or has_parsed_csvs):
            try:
                import sys
                project_root = os.path.dirname(os.path.abspath(__file__))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from scratch.build_precinct_crosswalk import build_canonical_crosswalk
                
                # If we have PDFs, use them. Otherwise, let build_canonical_crosswalk use fallbacks
                if reg_pdf_path and voting_pdf_path:
                    build_canonical_crosswalk(reg_pdf_path, voting_pdf_path, crosswalk_path)
                else:
                    build_canonical_crosswalk(output_path=crosswalk_path)
            except Exception as e:
                print(f"Self-healing crosswalk build failed: {e}")

    # Load crosswalk mapping
    cross_map = {}
    if os.path.exists(crosswalk_path):
        try:
            df_cross = pd.read_csv(crosswalk_path)
            for _, r in df_cross.iterrows():
                vp = str(r.get("Voter_PrecinctName", "")).strip()
                if vp.endswith(".0"):
                    vp = vp[:-2]
                if vp:
                    # Keep row in cross_map
                    cross_map[vp.upper()] = r
        except Exception as e:
            print(f"Failed to load crosswalk: {e}")

    # Normalize contest precincts
    df_contest = contest_df.copy()
    # Normalize PREC_JOIN as padded SOV precinct name
    df_contest['PREC_JOIN'] = df_contest[contest_prec_col].apply(lambda x: str(x).strip().zfill(7) if str(x).strip().isdigit() else str(x).strip().upper())
    
    # Map voter precincts in base to Voting Precinct using crosswalk
    prec_joins = []
    enrich_sources = []
    enrich_confidences = []
    prec_sources = []
    prec_assigned = []
    cross_src_files = []
    cross_match_rules = []
    cross_otm_flags = []
    result_inherited = []
    
    for idx, row in df_base.iterrows():
        pname = str(row.get("PrecinctName", "")).strip()
        if pname.endswith(".0"):
            pname = pname[:-2]
        pname_upper = pname.upper()
        
        xref_row = cross_map.get(pname_upper)
        if xref_row is not None and str(xref_row.get("Valid_For_Production", "")).upper() == "TRUE":
            voting_p = str(xref_row.get("Voting_Precinct", "")).strip()
            if voting_p.isdigit():
                voting_p = voting_p.zfill(7)
            prec_joins.append(voting_p.upper())


            
            rule = str(xref_row.get("Match_Rule", ""))
            cross_match_rules.append(rule)
            
            if rule == "exact_match":
                enrich_sources.append("exact_precinct_match")
                result_inherited.append(False)
            else:
                enrich_sources.append("official_crosswalk_inherited")
                result_inherited.append(True)
                
            enrich_confidences.append("high")
            prec_sources.append(os.path.basename(contest_file_path) if contest_file_path else "detail.csv")
            prec_assigned.append(voting_p)
            cross_src_files.append(f"{os.path.basename(reg_pdf_path)} / {os.path.basename(voting_pdf_path)}" if (reg_pdf_path and voting_pdf_path) else "ewmr010_regabsvotpctxref_2026-06-02.pdf / ewmr008_votabsregpctxref_2026-06-02.pdf")
            cross_otm_flags.append(str(xref_row.get("One_To_Many_Flag", "NO")))
        else:
            # Fall back to exact padded match
            p_padded = pname.zfill(7)
            if p_padded.upper() in df_contest['PREC_JOIN'].unique():
                prec_joins.append(p_padded.upper())
                enrich_sources.append("exact_precinct_match")
                enrich_confidences.append("high")
                prec_sources.append(os.path.basename(contest_file_path) if contest_file_path else "detail.csv")
                prec_assigned.append(p_padded)
                cross_src_files.append("None")
                cross_match_rules.append("exact_match")
                cross_otm_flags.append("NO")
                result_inherited.append(False)
            else:
                prec_joins.append("UNMAPPED_PRECINCT")
                enrich_sources.append("no_contest_match")
                enrich_confidences.append("none")
                prec_sources.append("None")
                prec_assigned.append("None")
                cross_src_files.append("None")
                cross_match_rules.append("None")
                cross_otm_flags.append("NO")
                result_inherited.append(False)
                
    df_base['PrecinctName_JOIN'] = prec_joins
    
    df_calc = pd.DataFrame({'PREC_JOIN': df_contest['PREC_JOIN'].unique()})
    
    components = {
        "Support": [],           # List of (weight, score_col)
        "Persuasion": [],
        "Turnout": [],
        "Issue_Alignment": []
    }
    
    contest_sources = []
    
    for idx, rule in enumerate(config):
        c_name = rule.get("contest_name", rule.get("name", f"Contest_{idx}"))
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
                    grouped = df_contest.groupby('PREC_JOIN').agg({
                        fav_col: lambda s: pd.to_numeric(s, errors='coerce').sum(),
                        opp_col: lambda s: pd.to_numeric(s, errors='coerce').sum()
                    })
                    fav_sum = grouped[fav_col]
                    opp_sum = grouped[opp_col]
                    tot = fav_sum + opp_sum
                    ratio = (fav_sum / tot.replace(0, np.nan)).fillna(0)
                    df_calc[calc_col] = df_calc['PREC_JOIN'].map(ratio)
                    
            elif c_type == "Initiative / ballot measure":
                fav_col = rule.get("favorable_col")
                tot_col = rule.get("total_col")
                if fav_col in df_contest.columns and tot_col in df_contest.columns:
                    grouped = df_contest.groupby('PREC_JOIN').agg({
                        fav_col: lambda s: pd.to_numeric(s, errors='coerce').sum(),
                        tot_col: lambda s: pd.to_numeric(s, errors='coerce').sum()
                    })
                    fav_sum = grouped[fav_col]
                    tot_sum = grouped[tot_col]
                    ratio = (fav_sum / tot_sum.replace(0, np.nan)).fillna(0)
                    df_calc[calc_col] = df_calc['PREC_JOIN'].map(ratio)
                    
            elif c_type == "Turnout":
                ballots_col = rule.get("ballots_col")
                reg_col = rule.get("reg_col")
                if ballots_col in df_contest.columns and reg_col in df_contest.columns:
                    grouped = df_contest.groupby('PREC_JOIN').agg({
                        ballots_col: lambda s: pd.to_numeric(s, errors='coerce').sum(),
                        reg_col: lambda s: pd.to_numeric(s, errors='coerce').sum()
                    })
                    ballots_sum = grouped[ballots_col]
                    reg_sum = grouped[reg_col]
                    ratio = (ballots_sum / reg_sum.replace(0, np.nan)).fillna(0)
                    df_calc[calc_col] = df_calc['PREC_JOIN'].map(ratio)
                    
            elif c_type == "Party baseline":
                fav_col = rule.get("favorable_col")
                tot_col = rule.get("total_col")
                if fav_col in df_contest.columns and tot_col in df_contest.columns:
                    grouped = df_contest.groupby('PREC_JOIN').agg({
                        fav_col: lambda s: pd.to_numeric(s, errors='coerce').sum(),
                        tot_col: lambda s: pd.to_numeric(s, errors='coerce').sum()
                    })
                    fav_sum = grouped[fav_col]
                    tot_sum = grouped[tot_col]
                    ratio = (fav_sum / tot_sum.replace(0, np.nan)).fillna(0)
                    df_calc[calc_col] = df_calc['PREC_JOIN'].map(ratio)
            
            if influence == "Confidence Only":
                continue
                
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
            pass

    df_merged = pd.merge(df_base, df_calc, left_on='PrecinctName_JOIN', right_on='PREC_JOIN', how='left')
    
    # Store crosswalk columns
    df_merged['Contest_Enrichment_Source'] = enrich_sources
    df_merged['Contest_Enrichment_Confidence'] = enrich_confidences
    df_merged['SOV_Precinct_Source'] = prec_sources
    df_merged['SOV_Precinct_Assigned'] = prec_assigned
    df_merged['Crosswalk_Source_File'] = cross_src_files
    df_merged['Crosswalk_Match_Rule'] = cross_match_rules
    df_merged['Crosswalk_One_To_Many_Flag'] = cross_otm_flags
    df_merged['Contest_Result_Is_Inherited'] = result_inherited
    df_merged['Vote_Estimation_Method'] = "none"
    df_merged['Estimated_Child_Votes'] = np.nan
    
    for comp_name, rules_list in components.items():
        score_col = f"Contest_{comp_name}_Score"
        df_merged[score_col] = np.nan
        
        if rules_list:
            w_sum = pd.Series(0.0, index=df_merged.index)
            val_sum = pd.Series(0.0, index=df_merged.index)
            
            for w, c_col in rules_list:
                mask = df_merged[c_col].notna()
                w_sum.loc[mask] += w
                val_sum.loc[mask] += w * df_merged.loc[mask, c_col]
                
            df_merged[score_col] = (val_sum / w_sum.replace(0, np.nan))
            
    total_classified_weight = sum([float(rule.get("weight", 0.5)) for rule in config])
    
    df_merged["Contest_Confidence"] = 0.0
    df_merged["Contest_Coverage_Flag"] = "no_contest_match"
    
    if total_classified_weight > 0:
        w_sum_overall = pd.Series(0.0, index=df_merged.index)
        for idx, rule in enumerate(config):
            c_name = rule.get("contest_name", rule.get("name", f"Contest_{idx}"))
            calc_col = f"Calc_{idx}_{c_name.replace(' ', '_')}"
            weight = float(rule.get("weight", 0.5))
            
            if calc_col in df_merged.columns:
                mask = df_merged[calc_col].notna()
                w_sum_overall.loc[mask] += weight
        
        df_merged["Contest_Confidence"] = w_sum_overall / total_classified_weight
        df_merged.loc[df_merged["Contest_Confidence"] > 0, "Contest_Coverage_Flag"] = "partial_contest_match"
        df_merged.loc[df_merged["Contest_Confidence"] >= 0.99, "Contest_Coverage_Flag"] = "full_contest_match"

    enrich_cols = [f"Contest_{comp_name}_Score" for comp_name in components.keys()]
    df_merged["Contest_Enrichment_Score"] = df_merged[enrich_cols].mean(axis=1)
    
    # Enforce no_contest_match if enrichment score is NaN
    df_merged.loc[df_merged["Contest_Enrichment_Score"].isna(), "Contest_Coverage_Flag"] = "no_contest_match"
    
    # Set Inherited_Support_Rate and Official_Parent_SOV_Total_Votes
    df_merged['Inherited_Support_Rate'] = np.nan
    df_merged.loc[df_merged['Contest_Result_Is_Inherited'] == True, 'Inherited_Support_Rate'] = df_merged['Contest_Support_Score']
    
    df_merged['Official_Parent_SOV_Total_Votes'] = np.nan
    parent_totals = {}
    if len(config) > 0:
        rule = config[0]
        fav_col = rule.get("favorable_col")
        opp_col = rule.get("opposition_col")
        if fav_col in df_contest.columns and opp_col in df_contest.columns:
            grouped_totals = df_contest.groupby('PREC_JOIN').apply(
                lambda df: pd.to_numeric(df[fav_col], errors='coerce').sum() + pd.to_numeric(df[opp_col], errors='coerce').sum()
            ).to_dict()
            parent_totals = grouped_totals
            
    df_merged['Official_Parent_SOV_Total_Votes'] = df_merged['PREC_JOIN'].map(parent_totals)

    has_enrich = df_merged["Contest_Enrichment_Score"].notna()
    df_merged["Final_Priority_Score"] = df_merged["Base_Priority_Score"]
    df_merged.loc[has_enrich, "Final_Priority_Score"] = (
        (1.0 - influence_weight) * df_merged.loc[has_enrich, "Base_Priority_Score"] +
        influence_weight * df_merged.loc[has_enrich, "Contest_Enrichment_Score"]
    )
    
    df_merged["Contest_Source_Summary"] = ", ".join(contest_sources) if contest_sources else "None"
    
    df_merged["Base_Rank"] = df_merged["Base_Priority_Score"].rank(ascending=False, method='min').astype(int)
    df_merged["Final_Rank"] = df_merged["Final_Priority_Score"].rank(ascending=False, method='min').astype(int)
    df_merged["Rank_Change"] = df_merged["Base_Rank"] - df_merged["Final_Rank"]
    
    drop_cols = [c for c in df_merged.columns if c.startswith("Calc_") or c in ['PrecinctName_JOIN', 'PREC_JOIN']]
    df_final = df_merged.drop(columns=drop_cols, errors='ignore')
    
    df_final = add_config_provenance_columns(df_final, config, contest_file_path, relationship=relationship)
    
    save_diagnostics(df_final, config, base_scored_df, df_contest, contest_prec_col, output_dir)
    
    return df_final


def save_diagnostics(df_final, config, base_scored_df, contest_df, contest_prec_col, output_dir):
    """
    Generates all diagnostic report files in outputs/contest_data_manager/
    """
    os.makedirs(output_dir, exist_ok=True)
    
    provenance_cols = [
        "Active_Contest_Config_Path",
        "Active_Contest_Config_Hash",
        "Active_Contest_Names",
        "Active_Contest_File_Path",
        "Active_Contest_File_Hash",
        "Contest_Config_Matches_Contest_File",
        "Contest_Config_Status"
    ]
    
    # 1. contest_scoring_breakdown.csv
    breakdown_cols = [
        "PrecinctName", "Base_Priority_Score", "Contest_Enrichment_Score", "Final_Priority_Score",
        "Contest_Support_Score", "Contest_Persuasion_Score", "Contest_Turnout_Score",
        "Contest_Issue_Alignment_Score", "Contest_Confidence"
    ] + provenance_cols
    df_final[breakdown_cols].to_csv(os.path.join(output_dir, "contest_scoring_breakdown.csv"), index=False)
    
    # 2. contest_coverage_report.csv
    cov_cols = ["PrecinctName", "Contest_Confidence", "Contest_Coverage_Flag", "Contest_Source_Summary"] + provenance_cols
    df_final[cov_cols].to_csv(os.path.join(output_dir, "contest_coverage_report.csv"), index=False)
    
    # 3. contest_rank_shift_report.csv
    shift_cols = ["PrecinctName", "Base_Rank", "Final_Rank", "Rank_Change", "Base_Priority_Score", "Final_Priority_Score", "Contest_Source_Summary"] + provenance_cols
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
