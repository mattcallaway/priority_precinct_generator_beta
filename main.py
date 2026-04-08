import pandas as pd
import numpy as np
import logging
import os

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
        logging.error(f"Failed to load city mapping: {e}")
        raise

    try:
        dist_df = pd.read_csv(CONFIG["DISTRICT_ASSIGNMENTS"])
        dist_df = normalize_columns(dist_df)
        inputs['dist'] = dist_df
        logging.info(f"Loaded district assignments: {len(dist_df)} rows.")
    except Exception as e:
        logging.error(f"Failed to load district assignments: {e}")
        raise

    # Validate essential columns
    required_voter_cols = ['precinctname', 'party', 'general24', 'general22']
    v_cols = [c.lower() for c in voter_df.columns]
    for c in required_voter_cols:
        if c not in v_cols:
            logging.error(f"CRITICAL: Missing required column {c} in voter file.")
            raise ValueError(f"Missing required column {c} in voter file.")
    
    return inputs

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

def score_precincts(df):
    logging.info("Step 7: Computing scoring fields")
    
    # Calculate base fields
    df['Turnout_Gap_2024'] = df['Total_Voters'] - df['Voted_2024']
    total_party = df['Dem'] + df['Rep'] + df['NPP'] + df['OtherParty']
    df['Dem_Share'] = (df['Dem'] / total_party.replace(0, np.nan)).fillna(0)
    
    # Competitive Index: 1.0 is perfectly balanced (0.5 dem share), 0.0 is entirely homogeneous
    df['Competitive_Index'] = 1 - abs(df['Dem_Share'] - 0.5) * 2
    df['Competitive_Index'] = df['Competitive_Index'].clip(lower=0, upper=1)
    
    # Norm components using min-max
    def min_max_norm(series):
        if series.max() == series.min():
            return pd.Series(0, index=series.index)
        return (series - series.min()) / (series.max() - series.min())
        
    tgap_norm = min_max_norm(df['Turnout_Gap_2024'])
    comp_norm = min_max_norm(df['Competitive_Index'])
    voter_norm = min_max_norm(df['Total_Voters'])
    
    # Priority Score Formula (Proof of concept)
    # Higher score prioritizing large numbers of low-turnout voters in a heavily competitive district
    df['Priority_Score'] = 0.45 * tgap_norm + 0.35 * comp_norm + 0.20 * voter_norm
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
    print(overlap_df[['SRPREC', 'CITY', 'Total_Voters', 'Turnout_Gap_2024', 'Competitive_Index', 'Priority_Score']].head(20).to_string())
    
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

def main():
    try:
        inputs = load_inputs()
        voter_flags = build_voter_flags(inputs['voters'])
        
        mprec_agg = aggregate_mprec(voter_flags)
        
        mprec_join = join_crosswalk(mprec_agg, inputs['mprec'])
        srprec_agg = aggregate_srprec(mprec_join)
        
        base_df = join_city_and_districts(srprec_agg, inputs['city'], inputs['dist'])
        score_df = score_precincts(base_df)
        
        export_outputs(voter_flags, mprec_agg, srprec_agg, base_df, score_df)
        
        logging.info("Pipeline completed successfully.")
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"Pipeline failed: {e}")

if __name__ == "__main__":
    main()
