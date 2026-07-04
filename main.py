import pandas as pd
import numpy as np
import logging
import os
from core_diagnostics import generate_diagnostic_outputs

# --- Configuration Section ---
CONFIG = {
    "VOTER_FILE": "data/voter_file.csv",
    "MPREC_CROSSWALK": "data/mprec_srprec.csv",
    "SRPREC_CITY": "data/srprec_city.csv",
    "DISTRICT_ASSIGNMENTS": "data/district_assignment.csv",
    "PRECINCT_METRICS": "data/srprec_metrics.csv",
    "OUTPUT_DIR": "outputs"
}

COUNTY_RULES = {
    "Sonoma": {
        "supervisorial_from_precinct_prefix": True
    }
}

os.makedirs(CONFIG["OUTPUT_DIR"], exist_ok=True)

logging.basicConfig(
    filename='run.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

QA_COLLECTIONS = {}
QA_METRICS = {}

def reset_qa():
    global QA_COLLECTIONS, QA_METRICS
    QA_COLLECTIONS.clear()
    QA_METRICS.clear()

def normalize_columns(df):
    df.columns = df.columns.str.strip().str.lower()
    return df

def generate_template():
    try:
        mprec_df = pd.read_csv(CONFIG["MPREC_CROSSWALK"])
        mprec_df = normalize_columns(mprec_df)
        unique_srprecs = mprec_df['srprec'].dropna().unique()
        
        dist_df = pd.DataFrame({
            'SRPREC': unique_srprecs,
            'assembly_district': [''] * len(unique_srprecs),
            'supervisorial_district': [''] * len(unique_srprecs)
        })
        dist_path = os.path.join(CONFIG["OUTPUT_DIR"], 'district_assignment_template.csv')
        dist_df.to_csv(dist_path, index=False)
        
        city_df = pd.DataFrame({
            'srprec': unique_srprecs,
            'city': [''] * len(unique_srprecs)
        })
        city_path = os.path.join(CONFIG["OUTPUT_DIR"], 'srprec_city_template.csv')
        city_df.to_csv(city_path, index=False)
        
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def is_mock_district_file(df, file_path=""):
    if df is None or df.empty:
        return False
    if "mock" in file_path.lower():
        return False
    first_col = df.columns[0]
    try:
        if df[first_col].astype(str).str.contains("SRPREC_").any():
            return True
    except:
        pass
    return False

def is_sonoma_context(voter_file_path, city_df=None):
    if "sonoma" in voter_file_path.lower():
        return True
    if city_df is not None and "county" in city_df.columns:
        try:
            if (city_df["county"] == 49).any() or (city_df["county"] == "49").any():
                return True
        except:
            pass
    return False

def find_voter_geo_columns(df):
    cols = {c.lower().strip(): c for c in df.columns}
    
    assembly_col = None
    for c in ['assembly_district', 'assembly district', 'assembly', 'ad']:
        if c in cols:
            assembly_col = cols[c]
            break
            
    senate_col = None
    for c in ['senate_district', 'senate district', 'senate', 'sd_senate', 'sen']:
        if c in cols:
            senate_col = cols[c]
            break
            
    supervisorial_col = None
    for c in ['supervisorial_district', 'supervisorial district', 'supervisorial', 'supervisor', 'sup_dist', 'sd']:
        if c in cols:
            supervisorial_col = cols[c]
            break
            
    city_col = None
    for c in ['city', 'mcity', 'municipality']:
        if c in cols:
            city_col = cols[c]
            break
            
    return {
        'assembly': assembly_col,
        'senate': senate_col,
        'supervisorial': supervisorial_col,
        'city': city_col
    }

def derive_sonoma_supervisorial(precinct_name):
    if pd.isna(precinct_name):
        return np.nan
    p_str = str(precinct_name).strip()
    if not p_str:
        return np.nan
    if len(p_str) == 7 and p_str.startswith('0'):
        val = p_str[:2]
    else:
        val = p_str[0]
    try:
        return int(val)
    except ValueError:
        return np.nan

def to_clean_district_str(val):
    if pd.isna(val) or val == '' or str(val).strip() == '' or str(val).lower() == 'nan' or str(val).lower() == 'unmapped':
        return 'Unmapped'
    try:
        f_val = float(val)
        if f_val.is_integer():
            return str(int(f_val))
        return str(f_val)
    except:
        return str(val).strip()

def generate_supervisorial_prefix_validation(voter_df, geo_cols, output_dir):
    p_col = None
    for c in voter_df.columns:
        if c.lower().strip() == 'precinctname':
            p_col = c
            break
    if not p_col:
        raise KeyError("Could not find precinctname column in voter file.")
        
    unique_precincts = voter_df[p_col].dropna().apply(to_clean_district_str).astype(str).str.strip().unique()
    
    records = []
    direct_col = geo_cols.get('supervisorial')
    
    direct_map = {}
    if direct_col:
        try:
            mode_df = voter_df.groupby(p_col)[direct_col].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else np.nan).dropna()
            direct_map = mode_df.to_dict()
        except Exception as e:
            logging.error(f"Error computing direct supervisorial modes: {e}")
            
    for p in unique_precincts:
        p_clean = p.strip()
        derived = derive_sonoma_supervisorial(p_clean)
        
        direct_val = np.nan
        if direct_col and p in direct_map:
            try:
                direct_val = int(float(direct_map[p]))
            except:
                direct_val = direct_map[p]
                
        match_status = "NO_DIRECT_FIELD"
        if pd.notna(direct_val):
            try:
                if int(derived) == int(float(direct_val)):
                    match_status = "MATCH"
                else:
                    match_status = "MISMATCH"
            except:
                match_status = "MISMATCH"
                
        records.append({
            "PrecinctName": p,
            "normalized_precinct": p_clean,
            "derived_supervisorial_district": derived if pd.notna(derived) else "",
            "direct_supervisorial_district_if_present": direct_val if pd.notna(direct_val) else "",
            "match_status": match_status,
            "source": "precinct_prefix_rule" if pd.notna(derived) else "unmapped",
            "confidence": "high_sonoma_verified" if pd.notna(derived) else "unknown"
        })
        
    report_df = pd.DataFrame(records)
    report_path = os.path.join(output_dir, "supervisorial_prefix_validation.csv")
    report_df.to_csv(report_path, index=False)
    logging.info(f"Prefix validation report saved to {report_path}")
    
    total_checked = len(report_df)
    compared_df = report_df[report_df['match_status'] != "NO_DIRECT_FIELD"]
    mismatches = compared_df[compared_df['match_status'] == "MISMATCH"]
    mismatch_count = len(mismatches)
    
    match_rate = 100.0
    if len(compared_df) > 0:
        match_rate = ((len(compared_df) - mismatch_count) / len(compared_df)) * 100
        
    return {
        "total_checked": total_checked,
        "compared_count": len(compared_df),
        "match_rate": match_rate,
        "mismatch_count": mismatch_count,
        "sample_mismatches": mismatches.head(5).to_dict(orient='records')
    }

def load_inputs(allow_mock=False):
    logging.info("Step 1: Loading input files")
    
    inputs = {}
    try:
        voter_df = pd.read_csv(CONFIG["VOTER_FILE"])
        inputs['voters'] = voter_df
        QA_METRICS['total_voter_rows'] = len(voter_df)
        
        required_voter_cols = ['precinctname', 'party', 'general24']
        v_cols = [c.lower() for c in voter_df.columns]
        for c in required_voter_cols:
            if c not in v_cols:
                raise ValueError(f"Missing required fundamental column {c} in voter file.")
                
        # Check Turnout dependencies
        if 'general22' in v_cols or any('2022' in c for c in v_cols):
            inputs['has_prior_turnout'] = True
        else:
            inputs['has_prior_turnout'] = False
            
    except Exception as e:
        logging.error(f"Failed to load voter file: {e}")
        raise

    try:
        mprec_df = pd.read_csv(CONFIG["MPREC_CROSSWALK"])
        mprec_df = normalize_columns(mprec_df)
        inputs['mprec'] = mprec_df
    except Exception as e:
        raise

    try:
        city_df = pd.read_csv(CONFIG["SRPREC_CITY"])
        inputs['city'] = normalize_columns(city_df)
    except Exception:
        inputs['city'] = None

    try:
        dist_path = CONFIG["DISTRICT_ASSIGNMENTS"]
        if os.path.exists(dist_path):
            dist_df = pd.read_csv(dist_path)
            if not allow_mock and is_mock_district_file(dist_df, dist_path):
                logging.warning("Mock district_assignment.csv detected. Ignoring for production scoring.")
                inputs['dist'] = None
            else:
                inputs['dist'] = normalize_columns(dist_df)
        else:
            mock_path = dist_path.replace(".csv", ".mock.csv")
            if allow_mock and os.path.exists(mock_path):
                dist_df = pd.read_csv(mock_path)
                inputs['dist'] = normalize_columns(dist_df)
            else:
                inputs['dist'] = None
    except Exception:
        inputs['dist'] = None
        
    try:
        metrics_df = pd.read_csv(CONFIG["PRECINCT_METRICS"])
        inputs['metrics'] = normalize_columns(metrics_df)
    except Exception:
        inputs['metrics'] = None
    
    return inputs

def build_voter_flags(df, has_prior_turnout, geo_cols_lower, derive_sonoma_sd=False):
    df_norm = df.copy()
    col_map = {c: c.strip().lower() for c in df_norm.columns}
    df_norm.rename(columns=col_map, inplace=True)
    
    df_norm['MPREC'] = df_norm['precinctname'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
    df_norm['Party_Clean'] = df_norm['party'].fillna('').astype(str).str.strip().str.upper()
    
    df_norm['Voted_2024_Flag'] = df_norm['general24'].fillna('').astype(str).str.strip().apply(lambda x: 1 if x != '' else 0)
    
    if has_prior_turnout:
        t2_col = [c for c in df_norm.columns if '22' in c or 'previous' in c][0]
        df_norm['Voted_Prior_Flag'] = df_norm[t2_col].fillna('').astype(str).str.strip().apply(lambda x: 1 if x != '' else 0)
    else:
        df_norm['Voted_Prior_Flag'] = 0
    
    df_norm['Dem_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['DEM', 'DEMOCRATIC', 'D'] else 0)
    df_norm['Rep_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['REP', 'REPUBLICAN', 'R'] else 0)
    df_norm['NPP_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['NPP', 'NO PARTY PREFERENCE', 'DECLINE TO STATE', 'DTS'] else 0)
    df_norm['OtherParty_Flag'] = 1 - (df_norm['Dem_Flag'] + df_norm['Rep_Flag'] + df_norm['NPP_Flag'])
    
    # Voter-file direct geography mapping or rules
    if geo_cols_lower.get('assembly'):
        df_norm['v_assembly'] = df_norm[geo_cols_lower['assembly']].fillna('')
    else:
        df_norm['v_assembly'] = np.nan
        
    if geo_cols_lower.get('senate'):
        df_norm['v_senate'] = df_norm[geo_cols_lower['senate']].fillna('')
    else:
        df_norm['v_senate'] = np.nan
        
    if geo_cols_lower.get('supervisorial'):
        df_norm['v_supervisorial'] = df_norm[geo_cols_lower['supervisorial']]
        df_norm['v_supervisorial_src'] = "voter_file_direct"
        df_norm['v_supervisorial_conf'] = "high"
    elif derive_sonoma_sd:
        df_norm['v_supervisorial'] = df_norm['precinctname'].apply(derive_sonoma_supervisorial)
        df_norm['v_supervisorial_src'] = "precinct_prefix_rule"
        df_norm['v_supervisorial_conf'] = "high_sonoma_verified"
    else:
        df_norm['v_supervisorial'] = np.nan
        df_norm['v_supervisorial_src'] = "unmapped"
        df_norm['v_supervisorial_conf'] = "unknown"
        
    if geo_cols_lower.get('city'):
        df_norm['v_city'] = df_norm[geo_cols_lower['city']].fillna('')
    else:
        df_norm['v_city'] = np.nan

    QA_METRICS['total_unique_mprecs'] = df_norm['MPREC'].nunique()
    return df_norm

def aggregate_mprec(df_voter):
    agg = df_voter.groupby('MPREC').agg({
        'MPREC': 'count',
        'Voted_2024_Flag': 'sum',
        'Voted_Prior_Flag': 'sum',
        'Dem_Flag': 'sum',
        'Rep_Flag': 'sum',
        'NPP_Flag': 'sum',
        'OtherParty_Flag': 'sum',
        'v_assembly': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_senate': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_supervisorial': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_supervisorial_src': lambda x: x.dropna().iloc[0] if not x.dropna().empty else 'unmapped',
        'v_supervisorial_conf': lambda x: x.dropna().iloc[0] if not x.dropna().empty else 'unknown',
        'v_city': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
    }).rename(columns={'MPREC': 'Total_Voters'}).reset_index()
    
    agg.rename(columns={
        'Voted_2024_Flag': 'Voted_Current',
        'Voted_Prior_Flag': 'Voted_Prior',
        'Dem_Flag': 'Dem',
        'Rep_Flag': 'Rep',
        'NPP_Flag': 'NPP',
        'OtherParty_Flag': 'OtherParty'
    }, inplace=True)
    return agg

def join_crosswalk(mprec_agg, mprec_cw):
    mprec_cw['mprec'] = mprec_cw['mprec'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
    mprec_cw['srprec'] = mprec_cw['srprec'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
    
    merged = pd.merge(mprec_agg, mprec_cw, left_on='MPREC', right_on='mprec', how='left')
    unmatched = merged[merged['srprec'].isna()]
    match_rate = ((len(merged) - len(unmatched)) / len(merged)) * 100 if len(merged) > 0 else 0
    
    QA_METRICS['mprec_input'] = len(merged)
    QA_METRICS['mprec_matched'] = len(merged) - len(unmatched)
    QA_METRICS['mprec_unmatched'] = len(unmatched)
    QA_METRICS['mprec_match_rate'] = f"{match_rate:.1f}%"
    
    if match_rate < 95.0:
        QA_METRICS.setdefault('pipeline_warnings', []).append(f"CRITICAL: MPREC match rate < 95% (Actual: {match_rate:.1f}%)")
        
    if not unmatched.empty:
        QA_COLLECTIONS['unmatched_mprec'] = unmatched[['MPREC', 'Total_Voters']]
        
    QA_METRICS['unmatched_mprecs_count'] = len(unmatched)
    merged.rename(columns={'srprec': 'SRPREC'}, inplace=True)
    return merged.dropna(subset=['SRPREC'])

def aggregate_srprec(mprec_mapped):
    agg = mprec_mapped.groupby('SRPREC').agg({
        'Total_Voters': 'sum',
        'Voted_Current': 'sum',
        'Voted_Prior': 'sum',
        'Dem': 'sum',
        'Rep': 'sum',
        'NPP': 'sum',
        'OtherParty': 'sum',
        'v_assembly': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_senate': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_supervisorial': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
        'v_supervisorial_src': lambda x: x.dropna().iloc[0] if not x.dropna().empty else 'unmapped',
        'v_supervisorial_conf': lambda x: x.dropna().iloc[0] if not x.dropna().empty else 'unknown',
        'v_city': lambda x: x.dropna().iloc[0] if not x.dropna().empty else np.nan,
    }).reset_index()
    QA_METRICS['total_unique_srprecs'] = len(agg)
    return agg

def apply_mappings(srprec_agg, city_cw, dist_cw, metrics_cw):
    df = srprec_agg.copy()
    
    # 1. City Assignment
    df['City_Source'] = df['v_city'].apply(lambda x: 'voter_file_direct' if pd.notna(x) and x != '' else 'unmapped')
    if city_cw is not None:
        city_cw['srprec'] = city_cw['srprec'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
        df = pd.merge(df, city_cw, left_on='SRPREC', right_on='srprec', how='left')
        df['city_ext'] = df['city']
        df.drop(columns=['city', 'srprec'], errors='ignore', inplace=True)
    else:
        df['city_ext'] = np.nan
        
    df['CITY'] = df['v_city'].fillna(df['city_ext']).fillna('Unmapped')
    df.loc[(df['City_Source'] == 'unmapped') & df['city_ext'].notna(), 'City_Source'] = 'external_mapping'
    df.drop(columns=['city_ext', 'v_city'], errors='ignore', inplace=True)
    
    # 2. Assembly District Assignment
    df['Assembly_District_Source'] = df['v_assembly'].apply(lambda x: 'voter_file_direct' if pd.notna(x) and x != '' else 'unmapped')
    if dist_cw is not None:
        dist_cw['srprec'] = dist_cw['srprec'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
        df = pd.merge(df, dist_cw, left_on='SRPREC', right_on='srprec', how='left')
        df.rename(columns={'assembly_district': 'assembly_ext'}, inplace=True)
        df.drop(columns=['srprec'], errors='ignore', inplace=True)
    else:
        df['assembly_ext'] = np.nan
        
    df['Assembly_District'] = df['v_assembly'].fillna(df['assembly_ext'])
    df['Assembly_District'] = df['Assembly_District'].apply(to_clean_district_str)
    df.loc[(df['Assembly_District_Source'] == 'unmapped') & df['assembly_ext'].notna(), 'Assembly_District_Source'] = 'external_mapping'
    df.drop(columns=['assembly_ext', 'v_assembly'], errors='ignore', inplace=True)
    
    # 3. Senate District Assignment
    df['Senate_District_Source'] = df['v_senate'].apply(lambda x: 'voter_file_direct' if pd.notna(x) and x != '' else 'unmapped')
    df['Senate_District'] = df['v_senate'].fillna('Unmapped')
    df['Senate_District'] = df['Senate_District'].apply(to_clean_district_str)
    df.drop(columns=['v_senate'], errors='ignore', inplace=True)
    
    # 4. Supervisorial District Assignment
    if dist_cw is not None:
        df.rename(columns={'supervisorial_district': 'supervisorial_ext'}, inplace=True)
    else:
        df['supervisorial_ext'] = np.nan
        
    df['Supervisorial_District'] = df['v_supervisorial'].fillna(df['supervisorial_ext'])
    df['Supervisorial_District'] = df['Supervisorial_District'].apply(to_clean_district_str)
    
    df['Supervisorial_District_Source'] = df['v_supervisorial_src']
    df['Supervisorial_District_Confidence'] = df['v_supervisorial_conf']
    
    external_mask = (df['Supervisorial_District_Source'] == 'unmapped') & df['supervisorial_ext'].notna()
    df.loc[external_mask, 'Supervisorial_District_Source'] = 'external_mapping'
    df.loc[external_mask, 'Supervisorial_District_Confidence'] = 'medium'
    
    df.drop(columns=['supervisorial_ext', 'v_supervisorial', 'v_supervisorial_src', 'v_supervisorial_conf'], errors='ignore', inplace=True)
    
    # 5. Metrics Assignment
    if metrics_cw is not None:
        metrics_cw['srprec'] = metrics_cw['srprec'].apply(to_clean_district_str).astype(str).str.strip().str.upper()
        df = pd.merge(df, metrics_cw, left_on='SRPREC', right_on='srprec', how='left')
        df.rename(columns={'area_sq_miles': 'Area_Sq_Miles'}, inplace=True)
        df.drop(columns=['srprec'], errors='ignore', inplace=True)
    else:
        df['Area_Sq_Miles'] = np.nan
        
    return df

def score_precincts(df, weights, has_prior_turnout):
    df['Has_Prior_Turnout'] = has_prior_turnout
    df['Has_Area'] = df['Area_Sq_Miles'].notna() & (df['Area_Sq_Miles'] > 0)
    
    if has_prior_turnout:
        df['Turnout_Dropoff_Rate'] = ((df['Voted_Prior'] - df['Voted_Current']) / df['Total_Voters'].replace(0, np.nan)).fillna(0)
    else:
        df['Turnout_Dropoff_Rate'] = 0.0
        
    df['True_Density'] = (df['Total_Voters'] / df['Area_Sq_Miles'].replace(0, np.nan)).fillna(0.0)
    
    total_party = df['Dem'] + df['Rep'] + df['NPP'] + df['OtherParty']
    df['Dem_Share'] = (df['Dem'] / total_party.replace(0, np.nan)).fillna(0)
    df['Rep_Share'] = (df['Rep'] / total_party.replace(0, np.nan)).fillna(0)
    
    df['Competitive_Index'] = 1 - abs(df['Dem_Share'] - df['Rep_Share'])
    df['Competitive_Index'] = df['Competitive_Index'].clip(lower=0, upper=1)
    
    def min_max_norm(series):
        s_min = series.min()
        s_max = series.max()
        if pd.isna(s_min) or pd.isna(s_max) or s_max == s_min:
            return pd.Series(0.0, index=series.index)
        return (series - s_min) / (s_max - s_min)
        
    df['Normalized_Turnout_Drop'] = min_max_norm(df['Turnout_Dropoff_Rate'])
    df['Normalized_Competitive_Index'] = min_max_norm(df['Competitive_Index'])
    df['Normalized_True_Density'] = min_max_norm(df['True_Density'])
    
    df['Used_Density'] = weights.get('density', 0) > 0
    df['Used_Underperformance'] = weights.get('turnout_gap', 0) > 0
    
    w_t = weights.get("turnout_gap", 0)
    w_c = weights.get("competitive_index", 0)
    w_d = weights.get("density", 0)
    
    df['Priority_Score'] = (w_t * df['Normalized_Turnout_Drop']) + (w_c * df['Normalized_Competitive_Index']) + (w_d * df['Normalized_True_Density'])
    df['Rank'] = df['Priority_Score'].rank(ascending=False, method='min').astype(int)
    
    return df.sort_values('Priority_Score', ascending=False)

def export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df, overlap_df, target_params, weights):
    wb_path = os.path.join(CONFIG['OUTPUT_DIR'], 'precinct_targeting_workbook.xlsx')
    with pd.ExcelWriter(wb_path, engine='openpyxl') as writer:
        if not overlap_df.empty:
            overlap_df.to_excel(writer, sheet_name='Filtered_Targets', index=False)
        else:
            pd.DataFrame({'Message': ['No precincts matched the selection.']}).to_excel(writer, sheet_name='Filtered_Targets', index=False)
            
        score_df.to_excel(writer, sheet_name='Full_County_Scores', index=False)
        base_df.to_excel(writer, sheet_name='Raw_Precinct_Base', index=False)
        mprec_agg.to_excel(writer, sheet_name='MPREC_Aggregates', index=False)
        voter_flags.head(500).to_excel(writer, sheet_name='Raw_Voter_Sample', index=False)
    
    overlap_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'target_precincts.csv'), index=False)
    
    exp_path = os.path.join(CONFIG['OUTPUT_DIR'], 'debug_explainer.txt')
    with open(exp_path, 'w', encoding='utf-8') as f:
        f.write("STRICT MATH EXPLAINER\n")
        f.write(f"Turnout Base Elasticity Weight: {weights.get('turnout_gap', 0)*100:.1f}%\n")
        f.write(f"Two-Party Competitiveness Weight: {weights.get('competitive_index', 0)*100:.1f}%\n")
        f.write(f"True Density (Area) Weight: {weights.get('density', 0)*100:.1f}%\n")
        f.write(f"Parameters Enforced: AD: {target_params.get('ad')}, SD: {target_params.get('sd')}, City: {target_params.get('city')}\n")

def run_pipeline(weights=None, target_params=None, allow_mock=False, county="Sonoma", derive_sonoma_sd=None, contest_file_path=None, contest_prec_col=None, contest_influence_weight=0.20):
    try:
        if target_params is None: target_params = {"ad": None, "sd": None, "city": None}
        if weights is None: weights = {"turnout_gap": 0.33, "competitive_index": 0.34, "density": 0.33}
        
        reset_qa()
        inputs = load_inputs(allow_mock=allow_mock)
        
        voter_df = inputs['voters']
        geo_cols = find_voter_geo_columns(voter_df)
        geo_cols_lower = {k: v.lower() if v else None for k, v in geo_cols.items()}
        
        # Determine Sonoma prefix-derivation rules
        is_sonoma = is_sonoma_context(CONFIG["VOTER_FILE"], inputs.get('city'))
        derive_rule_enabled = False
        if county in COUNTY_RULES and COUNTY_RULES[county].get("supervisorial_from_precinct_prefix"):
            derive_rule_enabled = True
        if derive_sonoma_sd is not None:
            derive_rule_enabled = derive_sonoma_sd
            
        # Run prefix validation report
        val_metrics = generate_supervisorial_prefix_validation(voter_df, geo_cols, CONFIG["OUTPUT_DIR"])
        
        if val_metrics["compared_count"] > 0 and val_metrics["match_rate"] < 98.0:
            msg = f"WARNING: Prefix-derived Supervisorial District does not match direct voter-file field reliably (Match Rate: {val_metrics['match_rate']:.1f}%). Do not use without review."
            QA_METRICS.setdefault('pipeline_warnings', []).append(msg)
            logging.warning(msg)
            
        voter_flags = build_voter_flags(voter_df, inputs['has_prior_turnout'], geo_cols_lower, derive_rule_enabled)
        mprec_agg = aggregate_mprec(voter_flags)
        mprec_join = join_crosswalk(mprec_agg, inputs['mprec'])
        srprec_agg = aggregate_srprec(mprec_join)
        
        base_df = apply_mappings(srprec_agg, inputs['city'], inputs['dist'], inputs['metrics'])
        
        score_df = score_precincts(base_df, weights, inputs['has_prior_turnout'])
        
        # Contest enrichment logic integration
        has_contest = False
        if contest_file_path and contest_prec_col and os.path.exists(contest_file_path):
            from contest_manager import load_classification_config, run_enrichment_calculations, inspect_and_load_file
            config = load_classification_config()
            if config:
                res_load = inspect_and_load_file(contest_file_path)
                if res_load["status"] == "success":
                    contest_df = res_load["df"]
                    score_df = run_enrichment_calculations(
                        score_df, 
                        contest_df, 
                        contest_prec_col, 
                        config, 
                        influence_weight=contest_influence_weight
                    )
                    has_contest = True
                    
        if not has_contest:
            score_df["Base_Priority_Score"] = score_df["Priority_Score"]
            score_df["Contest_Enrichment_Score"] = np.nan
            score_df["Final_Priority_Score"] = score_df["Priority_Score"]
            score_df["Contest_Support_Score"] = np.nan
            score_df["Contest_Persuasion_Score"] = np.nan
            score_df["Contest_Turnout_Score"] = np.nan
            score_df["Contest_Issue_Alignment_Score"] = np.nan
            score_df["Contest_Confidence"] = 0.0
            score_df["Contest_Coverage_Flag"] = "No Coverage"
            score_df["Contest_Source_Summary"] = "None"
            score_df["Base_Rank"] = score_df["Rank"]
            score_df["Final_Rank"] = score_df["Rank"]
            score_df["Rank_Change"] = 0
        
        # Extended Logic Validation Checks
        if not score_df.empty:
            if (score_df['Total_Voters'] == 0).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Found SRPRECs with 0 Total Voters.")
            if (score_df['Voted_Current'] > score_df['Total_Voters']).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Precincts found with Turnout > Registered Voters.")
                
        # Pure dynamic overlap logic
        overlap_df = score_df.copy()
        if target_params.get('ad') is not None:
            overlap_df = overlap_df[overlap_df['Assembly_District'].astype(str) == str(target_params['ad'])]
        if target_params.get('sd') is not None:
            overlap_df = overlap_df[overlap_df['Supervisorial_District'].astype(str) == str(target_params['sd'])]
        if target_params.get('city') is not None:
            overlap_df = overlap_df[overlap_df['CITY'].astype(str) == str(target_params['city'])]
            
        if overlap_df.empty:
            logging.warning("Overlap execution resulted in 0 rows.")
            
        export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df, overlap_df, target_params, weights)
        
        geo_meta = {
            "supervisorial": {
                "source": base_df['Supervisorial_District_Source'].iloc[0] if not base_df.empty else "unmapped",
                "confidence": base_df['Supervisorial_District_Confidence'].iloc[0] if not base_df.empty else "unknown"
            },
            "assembly": {
                "source": base_df['Assembly_District_Source'].iloc[0] if not base_df.empty else "unmapped",
                "confidence": "high" if not base_df.empty and base_df['Assembly_District_Source'].iloc[0] == "voter_file_direct" else ("medium" if not base_df.empty and base_df['Assembly_District_Source'].iloc[0] == "external_mapping" else "unknown")
            },
            "senate": {
                "source": base_df['Senate_District_Source'].iloc[0] if not base_df.empty else "unmapped",
                "confidence": "high" if not base_df.empty and base_df['Senate_District_Source'].iloc[0] == "voter_file_direct" else "unknown"
            },
            "city": {
                "source": base_df['City_Source'].iloc[0] if not base_df.empty else "unmapped",
                "confidence": "high" if not base_df.empty and base_df['City_Source'].iloc[0] == "voter_file_direct" else ("medium" if not base_df.empty and base_df['City_Source'].iloc[0] == "external_mapping" else "unknown")
            }
        }
        
        jd_data = {
            'step_name': ['MPREC_to_SRPREC'],
            'match_rate': [QA_METRICS.get('mprec_match_rate')]
        }
        
        state_dict = {
            'voter_flags': voter_flags,
            'mprec_agg': mprec_agg,
            'srprec_agg': srprec_agg,
            'base_df': base_df,
            'score_df': score_df,
            'top_precincts': overlap_df,
            'unmatched_mprec': QA_COLLECTIONS.get('unmatched_mprec', pd.DataFrame()),
            'join_diagnostics': pd.DataFrame(jd_data),
            'pipeline_warnings': QA_METRICS.get('pipeline_warnings', []),
            'weights': weights,
            'target_params': target_params
        }
        
        generate_diagnostic_outputs(CONFIG["OUTPUT_DIR"], state_dict)
        
        return {
            "status": "success",
            "qa_metrics": QA_METRICS.copy(),
            "top_precincts": overlap_df,
            "geo_sources": geo_meta
        }
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    run_pipeline()
