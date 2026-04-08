import pandas as pd
import numpy as np
import logging
import os
from core_diagnostics import generate_diagnostic_outputs

# --- Configuration Section ---
CONFIG = {
    # Update these paths to point to real data files if not using test data
    "VOTER_FILE": "data/voter_file.csv",
    "MPREC_CROSSWALK": "data/mprec_srprec.csv",
    "SRPREC_CITY": "data/srprec_city.csv",
    "DISTRICT_ASSIGNMENTS": "data/district_assignment.csv",
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
    """Normalize column names by stripping whitespace and mapping to standard names if needed."""
    df.columns = df.columns.str.strip().str.lower()
    return df

def load_inputs():
    logging.info("Step 1: Loading input files")
    
    inputs = {}
    try:
        voter_df = pd.read_csv(CONFIG["VOTER_FILE"])
        inputs['voters'] = voter_df
        logging.info(f"Loaded voter file: {len(voter_df)} rows. Columns: {list(voter_df.columns)}")
        QA_METRICS['total_voter_rows'] = len(voter_df)
    except Exception as e:
        logging.error(f"Failed to load voter file: {e}")
        raise

    try:
        mprec_df = pd.read_csv(CONFIG["MPREC_CROSSWALK"])
        mprec_df = normalize_columns(mprec_df)
        inputs['mprec'] = mprec_df
        logging.info(f"Loaded MPREC crosswalk: {len(mprec_df)} rows.")
    except Exception as e:
        logging.error(f"Failed to load MPREC crosswalk: {e}")
        raise

    try:
        city_df = pd.read_csv(CONFIG["SRPREC_CITY"])
        city_df = normalize_columns(city_df)
        inputs['city'] = city_df
        logging.info(f"Loaded SRPREC city mapping: {len(city_df)} rows.")
    except Exception as e:
        # Changed from silent swallow to explicit None. The runner explicitly validates this state on run.
        inputs['city'] = None

    try:
        dist_df = pd.read_csv(CONFIG["DISTRICT_ASSIGNMENTS"])
        dist_df = normalize_columns(dist_df)
        inputs['dist'] = dist_df
        logging.info(f"Loaded district assignments: {len(dist_df)} rows.")
    except Exception as e:
        inputs['dist'] = None

    # Validate essential columns
    required_voter_cols = ['precinctname', 'party', 'general24', 'general22']
    v_cols = [c.lower() for c in voter_df.columns]
    for c in required_voter_cols:
        if c not in v_cols:
            logging.error(f"CRITICAL: Missing required column {c} in voter file.")
            raise ValueError(f"Missing required column {c} in voter file.")
    
    return inputs

def validate_data(inputs):
    """
    Computes pre-flight checks on loaded data mapping percentages
    so the UI can warn the user before scoring runs.
    """
    warnings_list = []
    
    if inputs.get('dist') is None:
        warnings_list.append("DISTRICT_ASSIGNMENT_MISSING")
    
    if inputs.get('city') is None:
        warnings_list.append("CITY_MAPPING_MISSING")
        
    return warnings_list

def generate_template():
    """
    Looks at the MPREC crosswalk and generates template assignments
    for both Districts and Cities.
    """
    try:
        mprec_df = pd.read_csv(CONFIG["MPREC_CROSSWALK"])
        mprec_df = normalize_columns(mprec_df)
        unique_srprecs = mprec_df['srprec'].dropna().unique()
        
        # District Template
        dist_df = pd.DataFrame({
            'SRPREC': unique_srprecs,
            'assembly_district': [''] * len(unique_srprecs),
            'supervisorial_district': [''] * len(unique_srprecs)
        })
        dist_path = os.path.join(CONFIG["OUTPUT_DIR"], 'district_assignment_template.csv')
        dist_df.to_csv(dist_path, index=False)
        
        # City Template
        city_df = pd.DataFrame({
            'srprec': unique_srprecs,
            'city': [''] * len(unique_srprecs)
        })
        city_path = os.path.join(CONFIG["OUTPUT_DIR"], 'srprec_city_template.csv')
        city_df.to_csv(city_path, index=False)
        
        return {"status": "success", "dist_path": dist_path, "city_path": city_path}
    except Exception as e:
        return {"status": "error", "message": f"Could not generate templates. Need MPREC crosswalk first: {e}"}

def build_voter_flags(df):
    logging.info("Step 2: Building voter helper flags")
    
    # Ensure column names map correctly since they were originally loaded mixed case
    df_norm = df.copy()
    col_map = {c: c.strip().lower() for c in df_norm.columns}
    df_norm.rename(columns=col_map, inplace=True)
    
    df_norm['MPREC'] = df_norm['precinctname'].fillna('').astype(str).str.strip().str.upper()
    df_norm['Party_Clean'] = df_norm['party'].fillna('').astype(str).str.strip().str.upper()
    
    # Voted Flags
    df_norm['Voted_2024_Flag'] = df_norm['general24'].fillna('').astype(str).str.strip().apply(lambda x: 1 if x != '' else 0)
    df_norm['Voted_2022_Flag'] = df_norm['general22'].fillna('').astype(str).str.strip().apply(lambda x: 1 if x != '' else 0)
    
    # Party Flags
    df_norm['Dem_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['DEM', 'DEMOCRATIC', 'D'] else 0)
    df_norm['Rep_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['REP', 'REPUBLICAN', 'R'] else 0)
    df_norm['NPP_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['NPP', 'NO PARTY PREFERENCE', 'DECLINE TO STATE', 'DTS'] else 0)
    # Other Party
    df_norm['OtherParty_Flag'] = 1 - (df_norm['Dem_Flag'] + df_norm['Rep_Flag'] + df_norm['NPP_Flag'])
    
    QA_METRICS['total_unique_mprecs'] = df_norm['MPREC'].nunique()
    
    return df_norm

def aggregate_mprec(df_voter):
    logging.info("Step 3: Aggregating to MPREC")
    
    agg = df_voter.groupby('MPREC').agg({
        'MPREC': 'count',
        'Voted_2024_Flag': 'sum',
        'Voted_2022_Flag': 'sum',
        'Dem_Flag': 'sum',
        'Rep_Flag': 'sum',
        'NPP_Flag': 'sum',
        'OtherParty_Flag': 'sum'
    }).rename(columns={'MPREC': 'Total_Voters'}).reset_index()
    
    agg.rename(columns={
        'Voted_2024_Flag': 'Voted_2024',
        'Voted_2022_Flag': 'Voted_2022',
        'Dem_Flag': 'Dem',
        'Rep_Flag': 'Rep',
        'NPP_Flag': 'NPP',
        'OtherParty_Flag': 'OtherParty'
    }, inplace=True)
    
    agg['Turnout_Rate_2024'] = (agg['Voted_2024'] / agg['Total_Voters']).fillna(0)
    agg['Turnout_Rate_2022'] = (agg['Voted_2022'] / agg['Total_Voters']).fillna(0)
    
    return agg

def join_crosswalk(mprec_agg, mprec_cw):
    logging.info("Step 4: Joining MPREC to SRPREC crosswalk")
    
    # Ensure mapping formatting matches
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
        logging.warning(f"{len(unmatched)} MPRECs failed to map to an SRPREC.")
        QA_COLLECTIONS['unmatched_mprec'] = unmatched[['MPREC', 'Total_Voters']]
        QA_METRICS['unmatched_mprecs_count'] = len(unmatched)
    else:
        QA_METRICS['unmatched_mprecs_count'] = 0
        
    merged.rename(columns={'srprec': 'SRPREC'}, inplace=True)
    return merged.dropna(subset=['SRPREC'])

def aggregate_srprec(mprec_mapped):
    logging.info("Step 5: Aggregating to SRPREC")
    
    agg = mprec_mapped.groupby('SRPREC').agg({
        'Total_Voters': 'sum',
        'Voted_2024': 'sum',
        'Voted_2022': 'sum',
        'Dem': 'sum',
        'Rep': 'sum',
        'NPP': 'sum',
        'OtherParty': 'sum'
    }).reset_index()
    
    agg['Turnout_Rate_2024'] = (agg['Voted_2024'] / agg['Total_Voters']).fillna(0)
    agg['Turnout_Rate_2022'] = (agg['Voted_2022'] / agg['Total_Voters']).fillna(0)
    
    QA_METRICS['total_unique_srprecs'] = len(agg)
    return agg

def join_city_and_districts(srprec_agg, city_cw, dist_cw):
    logging.info("Step 6: Joining City and District assignments")
    
    city_cw['srprec'] = city_cw['srprec'].astype(str).str.strip().str.upper()
    city_cw['city'] = city_cw['city'].astype(str).str.strip()
    
    dist_cw['srprec'] = dist_cw['srprec'].astype(str).str.strip().str.upper()
    
    # Join City
    merged = pd.merge(srprec_agg, city_cw, left_on='SRPREC', right_on='srprec', how='left')
    unmatched_city = merged[merged['city'].isna()]
    if not unmatched_city.empty:
        logging.warning(f"{len(unmatched_city)} SRPRECs failed to map to a city.")
        QA_COLLECTIONS['unmatched_srprec_city'] = unmatched_city[['SRPREC', 'Total_Voters']]
    QA_METRICS['unmatched_srprecs_city_count'] = len(unmatched_city)
    
    merged.rename(columns={'city': 'CITY'}, inplace=True)
    merged.drop(columns=['srprec'], errors='ignore', inplace=True)
    
    # Join District
    merged = pd.merge(merged, dist_cw, left_on='SRPREC', right_on='srprec', how='left')
    unmatched_dist = merged[merged['assembly_district'].isna() | merged['supervisorial_district'].isna()]
    
    match_rate = ((len(merged) - len(unmatched_dist)) / len(merged)) * 100 if len(merged) > 0 else 0
    QA_METRICS['dist_input'] = len(merged)
    QA_METRICS['dist_matched'] = len(merged) - len(unmatched_dist)
    QA_METRICS['dist_unmatched'] = len(unmatched_dist)
    QA_METRICS['dist_match_rate'] = f"{match_rate:.1f}%"
    
    if match_rate < 95.0:
        QA_METRICS.setdefault('pipeline_warnings', []).append(f"CRITICAL: SRPREC district match rate < 95% (Actual: {match_rate:.1f}%)")
        
    if not unmatched_dist.empty:
        logging.warning(f"{len(unmatched_dist)} SRPRECs failed to map to districts.")
        QA_COLLECTIONS['unmatched_srprec_district'] = unmatched_dist[['SRPREC', 'Total_Voters']]
    QA_METRICS['unmatched_srprecs_district_count'] = len(unmatched_dist)
    
    merged.rename(columns={
        'assembly_district': 'Assembly_District',
        'supervisorial_district': 'Supervisorial_District'
    }, inplace=True)
    merged.drop(columns=['srprec'], errors='ignore', inplace=True)
    
    return merged

def score_precincts(df, weights=None):
    logging.info("Step 7: Computing scoring fields")
    
    if weights is None:
        weights = {"turnout_gap": 0.45, "competitive_index": 0.35, "density": 0.20}
    
    # Calculate base fields
    df['Turnout_Dropoff_Rate'] = ((df['Voted_2022'] - df['Voted_2024']) / df['Total_Voters'].replace(0, np.nan)).fillna(0)
    
    # Secure Total Party constraint
    total_party = df['Dem'] + df['Rep'] + df['NPP'] + df['OtherParty']
    df['Dem_Share'] = (df['Dem'] / total_party.replace(0, np.nan)).fillna(0)
    df['Rep_Share'] = (df['Rep'] / total_party.replace(0, np.nan)).fillna(0)
    
    # Competitiveness: 1.0 is perfectly tied spread between specifically Dem and Rep (ignoring sheer volume of NPP).
    df['Competitive_Index'] = 1 - abs(df['Dem_Share'] - df['Rep_Share'])
    df['Competitive_Index'] = df['Competitive_Index'].clip(lower=0, upper=1)
    
    # Norm components using safe min-max
    def min_max_norm(series):
        s_min = series.min()
        s_max = series.max()
        if pd.isna(s_min) or pd.isna(s_max) or s_max == s_min:
            return pd.Series(0.0, index=series.index)
        return (series - s_min) / (s_max - s_min)
        
    tdrop_norm = min_max_norm(df['Turnout_Dropoff_Rate'])
    comp_norm = min_max_norm(df['Competitive_Index'])
    voter_norm = min_max_norm(df['Total_Voters'])
    
    # Transparent normalized components
    df['Normalized_Turnout_Drop'] = tdrop_norm
    df['Normalized_Competitive_Index'] = comp_norm
    df['Normalized_Voter_Volume'] = voter_norm
    
    # Priority Score Formula
    df['Priority_Score'] = (weights["turnout_gap"] * tdrop_norm) + (weights["competitive_index"] * comp_norm) + (weights["density"] * voter_norm)
    df['Rank'] = df['Priority_Score'].rank(ascending=False, method='min').astype(int)
    
    # Sort
    return df.sort_values('Priority_Score', ascending=False)


def export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df):
    logging.info("Step 8 & 9: Exporting outputs")
    
    # Overlap df
    overlap_df = score_df[
        (score_df['Assembly_District'].astype(str) == '12.0') | (score_df['Assembly_District'].astype(str) == '12') &
        (score_df['Supervisorial_District'].astype(str) == '2.0') | (score_df['Supervisorial_District'].astype(str) == '2')
    ].copy()
    overlap_df.sort_values('Priority_Score', ascending=False, inplace=True)
    
    print("\nTop 20 Overlap Precincts (AD 12 / SD 2):")
    if not overlap_df.empty:
        print(overlap_df[['SRPREC', 'CITY', 'Total_Voters', 'Turnout_Dropoff_Rate', 'Competitive_Index', 'Priority_Score']].head(20).to_string())
    else:
        print("NO PRECINCTS FOUND WITHIN THIS DISTRICT BOUNDARY COMBINATION.")
    
    # Save CSVs
    mprec_agg.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'mprec_aggregate.csv'), index=False)
    srprec_agg.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'srprec_aggregate.csv'), index=False)
    base_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'precinct_base.csv'), index=False)
    score_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'scoring.csv'), index=False)
    overlap_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'overlap_ad12_sd2.csv'), index=False)
    for name, un_df in QA_COLLECTIONS.items():
        un_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], f"{name}.csv"), index=False)
    
    # Generate QA checks df
    qa_data = {
        'Metric': ['Total Voter Rows Read', 'Total Unique MPRECs', 'Total Unique SRPRECs', 
                   'Unmatched MPRECs Count', 'Unmatched SRPRECs (City)', 'Unmatched SRPRECs (District)'],
        'Value': [
            QA_METRICS.get('total_voter_rows', 0),
            QA_METRICS.get('total_unique_mprecs', 0),
            QA_METRICS.get('total_unique_srprecs', 0),
            QA_METRICS.get('unmatched_mprecs_count', 0),
            QA_METRICS.get('unmatched_srprecs_city_count', 0),
            QA_METRICS.get('unmatched_srprecs_district_count', 0)
        ]
    }
    qa_check_df = pd.DataFrame(qa_data)
    qa_check_df.to_csv(os.path.join(CONFIG['OUTPUT_DIR'], 'qa_checks.csv'), index=False)
    
    # Save to Excel
    wb_path = os.path.join(CONFIG['OUTPUT_DIR'], 'precinct_targeting_workbook.xlsx')
    with pd.ExcelWriter(wb_path, engine='openpyxl') as writer:
        # Avoid writing the entire voter file, only first 500 rows for sample
        voter_flags.head(500).to_excel(writer, sheet_name='Raw_Voter_Sample', index=False)
        voter_flags.to_excel(writer, sheet_name='Voter_With_Flags', index=False)
        mprec_agg.to_excel(writer, sheet_name='MPREC_Aggregate', index=False)
        srprec_agg.to_excel(writer, sheet_name='SRPREC_Aggregate', index=False)
        base_df.to_excel(writer, sheet_name='Precinct_Base', index=False)
        score_df.to_excel(writer, sheet_name='Scoring', index=False)
        overlap_df.to_excel(writer, sheet_name='Overlap_AD12_SD2', index=False)
        qa_check_df.to_excel(writer, sheet_name='QA_Checks', index=False)
        
    logging.info(f"Successfully generated {wb_path}")

def write_debug_explainer(weights):
    explainer_path = os.path.join(CONFIG['OUTPUT_DIR'], 'debug_explainer.txt')
    with open(explainer_path, 'w', encoding='utf-8') as f:
        f.write("=========================================\n")
        f.write("      PIPELINE EXECUTION EXPLAINER\n")
        f.write("=========================================\n\n")
        
        f.write("1. Data Flow & File Interactions:\n")
        f.write("--------------------------------\n")
        f.write("   - Read `voter_file.csv`. Filtered to 2022/2024 general election turnout and parsed party associations (Dem, Rep, NPP, Other).\n")
        f.write("   - Rolled individual voters up into their base Precinct (MPREC).\n")
        f.write("   - Matched each MPREC to a Master Supervisor Precinct (SRPREC) via `mprec_srprec.csv` crosswalk.\n")
        f.write("   - Grouped multiple MPRECs under unified SRPREC totals.\n")
        f.write("   - Joined each SRPREC to City boundaries using `srprec_city.csv` and to legislative boundaries using `district_assignment.csv`.\n\n")
        
        f.write("2. Mathematical Formulas Applied:\n")
        f.write("---------------------------------\n")
        f.write("   The Priority Score ranks precincts on three criteria against all other precincts using a normalized 0 to 1 scale.\n\n")
        
        f.write("   A. Turnout Dropoff Rate (Replaces 'Turnout Gap')\n")
        f.write("      Formula: (Voted_2022 - Voted_2024) / Total_Voters\n")
        f.write("      Why: Identifies elasticity. We highlight areas capable of voting but currently dormant, stripping away raw population bias.\n")
        f.write(f"      Current Weight Applied: {weights['turnout_gap']*100:.1f}%\n\n")
        
        f.write("   B. True Competitive Index\n")
        f.write("      Formula: 1 - |Dem Share - Rep Share|\n")
        f.write("      Why: Removes NPP independent dilution. Identifies extremely tight margins purely between the two engaged major parties.\n")
        f.write(f"      Current Weight Applied: {weights['competitive_index']*100:.1f}%\n\n")
        
        f.write("   C. Voter Volume (Replaces 'Density')\n")
        f.write("      Formula: Total Registered Voters inside SRPREC boundaries\n")
        f.write("      Why: Highly populated precincts have raw scaling advantages. (Note: Without explicit Area Polygon data, this measures magnitude, not geographic grouping).\n")
        f.write(f"      Current Weight Applied: {weights['density']*100:.1f}%\n\n")

        f.write("   Final Priority Score:\n")
        f.write(f"      ({weights['turnout_gap']} * Turnout Norm) + ({weights['competitive_index']} * Competitive Norm) + ({weights['density']} * Volume Norm)\n\n")

        f.write("3. Quality Assurance Diagnostics:\n")
        f.write("---------------------------------\n")
        f.write(f"   - Total Rows Loaded: {QA_METRICS.get('total_voter_rows', 0):,}\n")
        f.write(f"   - Total SRPRECs Mapped: {QA_METRICS.get('total_unique_srprecs', 0):,}\n")
        f.write(f"   - Failed MPREC Mappings: {QA_METRICS.get('unmatched_mprecs_count', 0):,} (Failed to link MPREC to an SRPREC)\n")
        f.write(f"   - Missing District Maps: {QA_METRICS.get('unmatched_srprecs_district_count', 0):,} (Linked to SRPREC but Assembly/Supervisorial district map entry was blank or missing)\n\n")
        
    logging.info(f"Successfully generated {explainer_path}")

def run_pipeline(weights=None):
    try:
        reset_qa()
        inputs = load_inputs()
        
        # Validation layer
        warnings = validate_data(inputs)
        if warnings:
            return {"status": "validation_error", "warnings": warnings}
            
        voter_flags = build_voter_flags(inputs['voters'])
        
        mprec_agg = aggregate_mprec(voter_flags)
        
        mprec_join = join_crosswalk(mprec_agg, inputs['mprec'])
        srprec_agg = aggregate_srprec(mprec_join)
        
        base_df = join_city_and_districts(srprec_agg, inputs['city'], inputs['dist'])
        score_df = score_precincts(base_df, weights)
        
        # weights might have been set to default if None
        if weights is None:
            weights = {"turnout_gap": 0.45, "competitive_index": 0.35, "density": 0.20}
            
        export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df)
        write_debug_explainer(weights)
        
        logging.info("Pipeline completed successfully.")
        
        # Extended Logic Validation Checks
        if not score_df.empty:
            if (score_df['Total_Voters'] == 0).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Found SRPRECs with 0 Total Voters.")
            if (score_df['Voted_2024'] > score_df['Total_Voters']).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Precints found with Turnout > Registered Voters.")
            if ((score_df['Dem'] + score_df['Rep'] + score_df['NPP']) > score_df['Total_Voters']).any():
                QA_METRICS.setdefault('pipeline_warnings', []).append("CRITICAL: Precincts found where Dem + Rep + NPP > Total Voters.")
        
        # Determine overlap dataframe to return to the UI
        overlap_df = score_df[
            (score_df['Assembly_District'].astype(str) == '12.0') | (score_df['Assembly_District'].astype(str) == '12') &
            (score_df['Supervisorial_District'].astype(str) == '2.0') | (score_df['Supervisorial_District'].astype(str) == '2')
        ].copy()
        overlap_df.sort_values('Priority_Score', ascending=False, inplace=True)
        
        # Consolidate join_diagnostics
        jd_data = {
            'step_name': ['MPREC_to_SRPREC', 'SRPREC_to_DISTRICT'],
            'input_rows': [QA_METRICS.get('mprec_input'), QA_METRICS.get('dist_input')],
            'matched_rows': [QA_METRICS.get('mprec_matched'), QA_METRICS.get('dist_matched')],
            'unmatched_rows': [QA_METRICS.get('mprec_unmatched'), QA_METRICS.get('dist_unmatched')],
            'match_rate': [QA_METRICS.get('mprec_match_rate'), QA_METRICS.get('dist_match_rate')]
        }
        join_diag_df = pd.DataFrame(jd_data)
        
        # State Dictionary for Diagnostics Output System
        state_dict = {
            'voter_flags': voter_flags,
            'mprec_agg': mprec_agg,
            'unmatched_mprec': QA_COLLECTIONS.get('unmatched_mprec', pd.DataFrame()),
            'srprec_agg': srprec_agg,
            'base_df': base_df,
            'unmatched_districts': QA_COLLECTIONS.get('unmatched_srprec_district', pd.DataFrame()),
            'score_df': score_df,
            'top_precincts': overlap_df,
            'join_diagnostics': join_diag_df,
            'pipeline_warnings': QA_METRICS.get('pipeline_warnings', []),
            'weights': weights
        }
        
        # Trigger the new comprehensive 12-file audit system
        summary_path = generate_diagnostic_outputs(CONFIG["OUTPUT_DIR"], state_dict)
        
        if summary_path:
            with open(summary_path, 'r', encoding='utf-8') as sf:
                print(sf.read())
        
        return {
            "status": "success",
            "qa_metrics": QA_METRICS.copy(),
            "qa_collections": QA_COLLECTIONS.copy(),
            "top_precincts": overlap_df
        }
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"Pipeline failed: {e}")
        return {"status": "error", "error": str(e)}

def main():
    run_pipeline()

if __name__ == "__main__":
    main()
