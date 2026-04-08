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

def load_inputs():
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
        dist_df = pd.read_csv(CONFIG["DISTRICT_ASSIGNMENTS"])
        inputs['dist'] = normalize_columns(dist_df)
    except Exception:
        inputs['dist'] = None
        
    try:
        metrics_df = pd.read_csv(CONFIG["PRECINCT_METRICS"])
        inputs['metrics'] = normalize_columns(metrics_df)
    except Exception:
        inputs['metrics'] = None
    
    return inputs

def build_voter_flags(df, has_prior_turnout):
    df_norm = df.copy()
    col_map = {c: c.strip().lower() for c in df_norm.columns}
    df_norm.rename(columns=col_map, inplace=True)
    
    df_norm['MPREC'] = df_norm['precinctname'].fillna('').astype(str).str.strip().str.upper()
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
        'OtherParty_Flag': 'sum'
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
    mprec_cw['mprec'] = mprec_cw['mprec'].astype(str).str.strip().str.upper()
    mprec_cw['srprec'] = mprec_cw['srprec'].astype(str).str.strip().str.upper()
    
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
        'OtherParty': 'sum'
    }).reset_index()
    QA_METRICS['total_unique_srprecs'] = len(agg)
    return agg

def apply_mappings(srprec_agg, city_cw, dist_cw, metrics_cw):
    df = srprec_agg.copy()
    
    if city_cw is not None:
        city_cw['srprec'] = city_cw['srprec'].astype(str).str.strip().str.upper()
        df = pd.merge(df, city_cw, left_on='SRPREC', right_on='srprec', how='left')
        df.rename(columns={'city': 'CITY'}, inplace=True)
        df.drop(columns=['srprec'], errors='ignore', inplace=True)
    else:
        df['CITY'] = 'Unmapped'
        
    if dist_cw is not None:
        dist_cw['srprec'] = dist_cw['srprec'].astype(str).str.strip().str.upper()
        df = pd.merge(df, dist_cw, left_on='SRPREC', right_on='srprec', how='left')
        df.rename(columns={
            'assembly_district': 'Assembly_District',
            'supervisorial_district': 'Supervisorial_District'
        }, inplace=True)
        df.drop(columns=['srprec'], errors='ignore', inplace=True)
    else:
        df['Assembly_District'] = 'Unmapped'
        df['Supervisorial_District'] = 'Unmapped'
        
    if metrics_cw is not None:
        metrics_cw['srprec'] = metrics_cw['srprec'].astype(str).str.strip().str.upper()
        df = pd.merge(df, metrics_cw, left_on='SRPREC', right_on='srprec', how='left')
        df.rename(columns={'area_sq_miles': 'Area_Sq_Miles'}, inplace=True)
        df.drop(columns=['srprec'], errors='ignore', inplace=True)
    else:
        df['Area_Sq_Miles'] = np.nan
        
    return df

def score_precincts(df, weights, has_prior_turnout):
    # TRUTH ENFORCEMENT
    df['Has_Prior_Turnout'] = has_prior_turnout
    df['Has_Area'] = df['Area_Sq_Miles'].notna() & (df['Area_Sq_Miles'] > 0)
    
    # Pre-Normalize Base Fields
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
    
    # Dependency Tracking Columns
    df['Used_Density'] = weights.get('density', 0) > 0
    df['Used_Underperformance'] = weights.get('turnout_gap', 0) > 0
    
    w_t = weights.get("turnout_gap", 0)
    w_c = weights.get("competitive_index", 0)
    w_d = weights.get("density", 0)
    
    df['Priority_Score'] = (w_t * df['Normalized_Turnout_Drop']) + (w_c * df['Normalized_Competitive_Index']) + (w_d * df['Normalized_True_Density'])
    df['Rank'] = df['Priority_Score'].rank(ascending=False, method='min').astype(int)
    
    return df.sort_values('Priority_Score', ascending=False)

def export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df, overlap_df, target_params, weights):
    # Re-writing Excel dynamically without assuming tabs
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
    
    # Save CSVs natively
    overlap_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'target_precincts.csv'), index=False)
    
    exp_path = os.path.join(CONFIG['OUTPUT_DIR'], 'debug_explainer.txt')
    with open(exp_path, 'w', encoding='utf-8') as f:
        f.write("STRICT MATH EXPLAINER\n")
        f.write(f"Turnout Base Elasticity Weight: {weights.get('turnout_gap', 0)*100:.1f}%\n")
        f.write(f"Two-Party Competitiveness Weight: {weights.get('competitive_index', 0)*100:.1f}%\n")
        f.write(f"True Density (Area) Weight: {weights.get('density', 0)*100:.1f}%\n")
        f.write(f"Parameters Enforced: AD: {target_params.get('ad')}, SD: {target_params.get('sd')}, City: {target_params.get('city')}\n")

def run_pipeline(weights=None, target_params=None):
    try:
        if target_params is None: target_params = {"ad": None, "sd": None, "city": None}
        if weights is None: weights = {"turnout_gap": 0.33, "competitive_index": 0.34, "density": 0.33}
        
        reset_qa()
        inputs = load_inputs()
        
        voter_flags = build_voter_flags(inputs['voters'], inputs['has_prior_turnout'])
        mprec_agg = aggregate_mprec(voter_flags)
        mprec_join = join_crosswalk(mprec_agg, inputs['mprec'])
        srprec_agg = aggregate_srprec(mprec_join)
        
        base_df = apply_mappings(srprec_agg, inputs['city'], inputs['dist'], inputs['metrics'])
        
        score_df = score_precincts(base_df, weights, inputs['has_prior_turnout'])
        
        # Extended Logic Validation Checks
        if not score_df.empty:
            if (score_df['Total_Voters'] == 0).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Found SRPRECs with 0 Total Voters.")
            if (score_df['Voted_Current'] > score_df['Total_Voters']).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Precints found with Turnout > Registered Voters.")
                
        # Pure dynamic overlap logic
        overlap_df = score_df.copy()
        if target_params.get('ad') is not None:
            overlap_df = overlap_df[overlap_df['Assembly_District'].astype(str) == str(target_params['ad'])]
        if target_params.get('sd') is not None:
            overlap_df = overlap_df[overlap_df['Supervisorial_District'].astype(str) == str(target_params['sd'])]
        if target_params.get('city') is not None:
            overlap_df = overlap_df[overlap_df['CITY'].astype(str) == str(target_params['city'])]
            
        if overlap_df.empty:
            # We strictly catch and return valid empty, let the UI handle the halt.
            logging.warning("Overlap execution resulted in 0 rows.")
            
        export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df, overlap_df, target_params, weights)
        
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
            "top_precincts": overlap_df
        }
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    run_pipeline()
