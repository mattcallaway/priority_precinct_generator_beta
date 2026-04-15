import pandas as pd
import numpy as np
import logging
import os
from core_diagnostics import generate_diagnostic_outputs

# --- Configuration Section ---
CONFIG = {
    "VOTER_FILE": "data/voter_file.csv",
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
    return {"status": "success", "message": "Template generation deprecated in voter-centric model."}

def load_inputs(column_map):
    logging.info("Step 1: Loading Voter File using Explicit Mode Mapping")
    inputs = {}
    try:
        voter_df = pd.read_csv(CONFIG["VOTER_FILE"], dtype=str)
        inputs['voters'] = voter_df
        QA_METRICS['total_voter_rows'] = len(voter_df)
        
        req_col = column_map.get('precinctname')
        if not req_col or req_col not in voter_df.columns:
            raise ValueError(f"Missing required fundamental column for PrecinctName: {req_col}")
            
    except Exception as e:
        logging.error(f"Failed to load voter file: {e}")
        raise
    return inputs

def build_voter_flags(df, column_map):
    df_norm = df.copy()
    
    df_norm['PrecinctName'] = df_norm[column_map['precinctname']].fillna('UNKNOWN').astype(str).str.strip().str.upper()
    
    party_col = column_map.get('party')
    if party_col and party_col in df_norm.columns:
        df_norm['Party_Clean'] = df_norm[party_col].fillna('').astype(str).str.strip().str.upper()
    else:
        df_norm['Party_Clean'] = 'UNKNOWN'
    
    # Flags multi-mapping
    df_norm['Presidential_Flag'] = 0
    if 'presidential_cols' in column_map:
        for c in column_map['presidential_cols']:
            if c in df_norm.columns:
                flag = (df_norm[c].fillna('').astype(str).str.strip() != '').astype(int)
                df_norm['Presidential_Flag'] |= flag

    df_norm['Midterm_Flag'] = 0
    if 'midterm_cols' in column_map:
        for c in column_map['midterm_cols']:
            if c in df_norm.columns:
                flag = (df_norm[c].fillna('').astype(str).str.strip() != '').astype(int)
                df_norm['Midterm_Flag'] |= flag
    
    df_norm['Dem_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['DEM', 'DEMOCRATIC', 'D'] else 0)
    df_norm['Rep_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['REP', 'REPUBLICAN', 'R'] else 0)
    df_norm['NPP_Flag'] = df_norm['Party_Clean'].apply(lambda x: 1 if x in ['NPP', 'NO PARTY PREFERENCE', 'DECLINE TO STATE', 'DTS'] else 0)
    df_norm['OtherParty_Flag'] = 1 - (df_norm['Dem_Flag'] + df_norm['Rep_Flag'] + df_norm['NPP_Flag'])
    
    # Explicit District Identification
    def extract_mapped_col(col_key):
        cname = column_map.get(col_key)
        if cname and cname in df_norm.columns:
            return df_norm[cname].fillna('Unmapped').astype(str).replace('', 'Unmapped')
        return pd.Series('Unmapped', index=df_norm.index)

    df_norm['Assembly_District'] = extract_mapped_col('assembly')
    df_norm['Senate_District'] = extract_mapped_col('senate')
    df_norm['Supervisorial_District'] = extract_mapped_col('supervisorial')
    df_norm['City'] = extract_mapped_col('city')
    
    QA_METRICS['total_unique_precincts'] = df_norm['PrecinctName'].nunique()
    return df_norm

def aggregate_precincts(df_voter):
    def mode_fallback(x):
        return x.mode().iloc[0] if not x.mode().empty else 'Unmapped'
        
    agg = df_voter.groupby('PrecinctName').agg(
        Total_Voters=('PrecinctName', 'count'),
        Voted_Presidential=('Presidential_Flag', 'sum'),
        Voted_Midterm=('Midterm_Flag', 'sum'),
        DEM=('Dem_Flag', 'sum'),
        REP=('Rep_Flag', 'sum'),
        NPP=('NPP_Flag', 'sum'),
        OtherParty=('OtherParty_Flag', 'sum'),
        Assembly_District=('Assembly_District', mode_fallback),
        Senate_District=('Senate_District', mode_fallback),
        Supervisorial_District=('Supervisorial_District', mode_fallback),
        City=('City', mode_fallback)
    ).reset_index()
    return agg

MIN_VIABLE_VOTERS = 50

def score_precincts(df, weights, target_params=None, ciab_tps_col=None, ciab_ps_col=None):
    df_score = df.copy()
    
    # Size Penalty & Viability
    df_score['Viability_Flag'] = df_score['Total_Voters'].apply(lambda x: 'too_small' if x < MIN_VIABLE_VOTERS else 'viable')
    df_score['Size_Factor'] = np.clip(df_score['Total_Voters'] / 150.0, 0.0, 1.0)
    
    # Advanced Election Turnout Rates
    df_score['Presidential_Turnout_Rate'] = (df_score['Voted_Presidential'] / df_score['Total_Voters'].replace(0, np.nan)).fillna(0)
    df_score['Midterm_Turnout_Rate'] = (df_score['Voted_Midterm'] / df_score['Total_Voters'].replace(0, np.nan)).fillna(0)
    
    df_score['Midterm_Underperformance'] = np.maximum(0, df_score['Presidential_Turnout_Rate'] - df_score['Midterm_Turnout_Rate'])
    df_score['Expansion_Underperformance'] = np.maximum(0, 1.0 - df_score['Presidential_Turnout_Rate'])
    
    w_m_drop = weights.get("midterm_dropoff_weight", 0.6)
    w_e_drop = weights.get("expansion_weight", 0.4)
    
    # Expected Votes Gained composite
    df_score['Expected_Votes_Gained'] = (df_score['Midterm_Underperformance'] * w_m_drop + df_score['Expansion_Underperformance'] * w_e_drop) * df_score['Total_Voters']
    df_score['Expected_Votes_Gained_Adjusted'] = df_score['Expected_Votes_Gained'] * df_score['Size_Factor']
    
    df_score['Turnout_Opportunity_Raw'] = (df_score['Midterm_Underperformance'] * w_m_drop + df_score['Expansion_Underperformance'] * w_e_drop) * np.sqrt(df_score['Total_Voters'].astype(float))
    
    # Dem Density Proxy
    df_score['Dem_Share'] = (df_score['DEM'] / df_score['Total_Voters'].replace(0, np.nan)).fillna(0)
    df_score['Dem_Volume'] = df_score['DEM']
    df_score['Target_Density_Proxy'] = df_score['Dem_Share']
    
    # Persuasion Potential
    df_score['TwoParty_Total'] = df_score['DEM'] + df_score['REP']
    
    def calculate_persuasion(row):
        total_2p = row['TwoParty_Total']
        if total_2p == 0:
            return 0.0
        dem_share = row['DEM'] / total_2p
        rep_share = row['REP'] / total_2p
        competitiveness = 1.0 - abs(dem_share - rep_share)
        two_party_share = total_2p / row['Total_Voters'] if row['Total_Voters'] > 0 else 0
        return competitiveness * two_party_share

    df_score['Competitiveness'] = df_score.apply(lambda r: 1.0 - abs((r['DEM'] / r['TwoParty_Total']) - (r['REP'] / r['TwoParty_Total'])) if r['TwoParty_Total'] > 0 else 0.0, axis=1)
    df_score['Persuasion_Potential'] = df_score.apply(calculate_persuasion, axis=1)
    
    # Efficiency Proxy
    df_score['Efficiency_Proxy'] = np.log1p(df_score['Total_Voters'])
    
    # Normalization (Min-Max)
    def min_max_norm(series):
        s_min = series.min()
        s_max = series.max()
        if pd.isna(s_min) or pd.isna(s_max) or s_max == s_min:
            return pd.Series(0.0, index=series.index)
        return (series - s_min) / (s_max - s_min)
        
    df_score['Turnout_Norm'] = min_max_norm(df_score['Turnout_Opportunity_Raw'])
    df_score['Persuasion_Norm'] = min_max_norm(df_score['Persuasion_Potential'])
    df_score['Efficiency_Norm'] = min_max_norm(df_score['Efficiency_Proxy'])
    df_score['Target_Density_Norm'] = min_max_norm(df_score['Target_Density_Proxy'])
    
    w_t = weights.get("turnout", 0.35)
    w_p = weights.get("persuasion", 0.25)
    w_e = weights.get("efficiency", 0.15)
    w_d = weights.get("target_density", 0.25)
    
    df_score['Priority_Score_PrePenalty'] = (w_t * df_score['Turnout_Norm']) + (w_p * df_score['Persuasion_Norm']) + (w_e * df_score['Efficiency_Norm']) + (w_d * df_score['Target_Density_Norm'])
    df_score['Priority_Score'] = df_score['Priority_Score_PrePenalty'] * df_score['Size_Factor']
    df_score['Rank'] = df_score['Priority_Score'].rank(ascending=False, method='min').astype(int)
    
    def build_reason(row):
        if row['Total_Voters'] < MIN_VIABLE_VOTERS:
            return "Tiny precinct highly penalized for low operational scale."
        reasons = []
        if row['Expected_Votes_Gained'] > 15:
            reasons.append("high turnout recovery potential")
        if row['Competitiveness'] > 0.6:
            reasons.append("contestable margins")
        if row['Dem_Share'] > 0.6:
            reasons.append("strong Democratic concentration")            
        
        if not reasons:
            return "Standard precinct with moderate operational metrics."
        
        if len(reasons) == 1:
            return f"Precinct defined by {reasons[0]}."
        elif len(reasons) == 2:
            return f"Precinct with {reasons[0]} and {reasons[1]}."
        return f"Precinct with {reasons[0]}, {reasons[1]}, and {reasons[2]}."

    df_score['Priority_Reason'] = df_score.apply(build_reason, axis=1)
    
    # Additional Context Fields
    df_score['data_source'] = 'voter_file'
    df_score['confidence'] = 'high'
    df_score['method'] = 'direct_field_assignment'
    
    return df_score.sort_values('Priority_Score', ascending=False)

def export_outputs(score_df, overlap_df, target_params, weights, execution_mode, output_dir=None):
    out = output_dir or CONFIG["OUTPUT_DIR"]
    summary_cols = [
        'PrecinctName', 'Assembly_District', 'Senate_District', 'Supervisorial_District', 'City',
        'Total_Voters', 'Voted_Presidential', 'Voted_Midterm', 'Presidential_Turnout_Rate', 'Midterm_Turnout_Rate',
        'Midterm_Underperformance', 'Expansion_Underperformance', 'Turnout_Opportunity_Raw',
        'Expected_Votes_Gained', 'Expected_Votes_Gained_Adjusted',
        'DEM', 'REP', 'NPP', 'OtherParty', 'Dem_Share', 'Dem_Volume', 'Target_Density_Proxy',
        'TwoParty_Total', 'Competitiveness', 'Persuasion_Potential', 'Efficiency_Proxy',
        'Size_Factor', 'Viability_Flag', 'Turnout_Norm', 'Persuasion_Norm', 'Efficiency_Norm', 'Target_Density_Norm',
        'Priority_Score', 'Rank', 'Priority_Reason', 'data_source', 'confidence', 'method'
    ]
    
    # Fill in missing cols if any to pass structured checks
    for c in summary_cols:
        if c not in score_df.columns:
            score_df[c] = pd.NA
            
    summary_df = score_df[summary_cols]
    summary_df.to_csv(os.path.join(out, 'precinct_scores.csv'), index=False)
    summary_df.to_csv(os.path.join(out, 'precinct_summary.csv'), index=False)  # fallback compat
    
    if not overlap_df.empty:
        overlap_df = overlap_df[summary_cols]
        top10 = overlap_df.head(10)
        with open(os.path.join(out, 'top10_sanity_check.md'), 'w', encoding='utf-8') as f:
            f.write("# Top 10 Ranked Precincts Sanity Check\n\n")
            for idx, row in top10.iterrows():
                flag = "🚩 WARNING: Suspicious metrics" if row['Total_Voters'] < 50 or row['Expected_Votes_Gained'] < 2 or row['Competitiveness'] == 0 else "✅ Passed"
                f.write(f"## Rank {row['Rank']}. {row['PrecinctName']} ({flag})\n")
                f.write(f"- **Size**: {row['Total_Voters']} voters (Viability: {row['Viability_Flag']})\n")
                f.write(f"- **Expected Votes Gained**: {row['Expected_Votes_Gained']:.1f}\n")
                f.write(f"- **Competitiveness**: {row['Competitiveness']:.2f}\n")
                f.write(f"- **Democratic Concentration**: {row['Dem_Share']*100:.1f}%\n")
                f.write(f"- **Algorithm Reason**: {row['Priority_Reason']}\n\n")

        suspicious = overlap_df[(overlap_df['Total_Voters'] < 50) | (overlap_df['Expected_Votes_Gained'] < 2) | (overlap_df['Competitiveness'] == 0) | ((overlap_df['DEM'] == 0) & (overlap_df['REP'] == 0)) | ((overlap_df['Priority_Score'] > 0.8) & (overlap_df['Total_Voters'] < 100))]
        with open(os.path.join(out, 'scoring_validation_report.txt'), 'w', encoding='utf-8') as f:
            f.write(f"VOTER-CENTRIC SCORING VALIDATION REPORT\n")
            f.write(f"Found {len(suspicious)} explicitly flagged irregular/suspicious rows within requested filters.\n\n")
            if len(suspicious) > 0:
                 f.write(suspicious[['PrecinctName', 'Total_Voters', 'Expected_Votes_Gained', 'Competitiveness']].to_string())
            else:
                 f.write("No severe anomalies detected in targeting bounds.\n")
    
    wb_path = os.path.join(out, 'precinct_targeting_workbook.xlsx')
    with pd.ExcelWriter(wb_path, engine='openpyxl') as writer:
        if not overlap_df.empty:
            overlap_df.to_excel(writer, sheet_name='Filtered_Targets', index=False)
        else:
            pd.DataFrame({'Message': ['No precincts matched the selection.']}).to_excel(writer, sheet_name='Filtered_Targets', index=False)
            
        summary_df.to_excel(writer, sheet_name='Full_County_Scores', index=False)
        score_df.to_excel(writer, sheet_name='Precinct_Stats_Detailed', index=False)
    
    if not overlap_df.empty:
        overlap_df.to_csv(os.path.join(out, 'top_precincts.csv'), index=False)
    
    exp_path = os.path.join(out, 'scoring_breakdown.txt')
    with open(exp_path, 'w', encoding='utf-8') as f:
        f.write(f"EXECUTION MODE: {execution_mode}\n\n")
        f.write("TARGET DRIVEN EXPLAINER\n")
        f.write(f"Turnout Weight       : {weights.get('turnout', 0)*100:.1f}%\n")
        f.write(f"Persuasion Weight    : {weights.get('persuasion', 0)*100:.1f}%\n")
        f.write(f"Efficiency Weight    : {weights.get('efficiency', 0)*100:.1f}%\n")
        f.write(f"Dem. Density Weight  : {weights.get('target_density', 0)*100:.1f}%\n")
        f.write(f"Filters Enforced     : {target_params}\n")

def run_pipeline(column_map=None, weights=None, target_params=None):
    try:
        if column_map is None: 
            column_map = {'precinctname': 'precinctname'} # Strict minimal
        if target_params is None: 
            target_params = {"assembly": None, "supervisorial": None, "senate": None, "city": None}
        if weights is None: 
            weights = {"turnout": 0.35, "persuasion": 0.25, "efficiency": 0.15, "target_density": 0.25, "midterm_dropoff_weight": 0.6, "expansion_weight": 0.4}
            
        reset_qa()
        inputs = load_inputs(column_map)
        
        voter_flags = build_voter_flags(inputs['voters'], column_map)
        base_df = aggregate_precincts(voter_flags)
        
        overlap_df = base_df.copy()
        for key, df_col in [('assembly', 'Assembly_District'), ('supervisorial', 'Supervisorial_District'), 
                            ('senate', 'Senate_District'), ('city', 'City')]:
            req_val = target_params.get(key)
            if req_val is not None and str(req_val).strip().upper() != 'ALL':
                overlap_df = overlap_df[overlap_df[df_col].astype(str).str.strip().str.upper() == str(req_val).strip().upper()]
            
        if overlap_df.empty:
            logging.warning("Overlap execution resulted in 0 rows (No precincts matched current filters).")
            
        score_df = score_precincts(overlap_df, weights)
        overlap_df = score_df.copy()
            
        # Determine strict mode logic based on inputs mapped
        has_dist = any([column_map.get('assembly'), column_map.get('senate'), column_map.get('supervisorial')])
        execution_mode = "Voter-Centric Mode" if has_dist else "Geometry-Dependent Mode (Required for Districts)"
            
        export_outputs(score_df, overlap_df, target_params, weights, execution_mode)
        
        jd_data = {'step_name': ['Voter_Aggregation'], 'precincts_scored': [len(score_df)]}
        
        geo_qa = []
        for d in ['Assembly_District', 'Senate_District', 'Supervisorial_District', 'City']:
            m = len(score_df[score_df[d] != 'Unmapped'])
            um = len(score_df) - m
            cov = (m / len(score_df)) * 100 if len(score_df)>0 else 0
            geo_qa.append({
                'Dimension': d,
                'Mapped_Precincts': m,
                'Unmapped_Precincts': um,
                'Coverage_Percent': f"{cov:.1f}%",
            })
        geo_report = pd.DataFrame(geo_qa)
        geo_report.to_csv(os.path.join(CONFIG.get('OUTPUT_DIR', 'outputs'), 'geography_coverage_report.csv'), index=False)
        QA_COLLECTIONS['geography_coverage'] = geo_report

        state_dict = {
            'voter_flags': voter_flags,
            'score_df': score_df,
            'top_precincts': overlap_df,
            'join_diagnostics': pd.DataFrame(jd_data),
            'pipeline_warnings': QA_METRICS.get('pipeline_warnings', []),
            'weights': weights,
            'target_params': target_params
        }
        
        try:
            generate_diagnostic_outputs(CONFIG["OUTPUT_DIR"], state_dict)
        except Exception as q_e:
            logging.warning(f"Failed partial diagnostics: {q_e}")
        
        return {
            "status": "success",
            "qa_metrics": QA_METRICS.copy(),
            "top_precincts": overlap_df,
            "execution_mode": execution_mode
        }
    except Exception as e:
        logging.error(f"Pipeline crashed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    # Test strict mapping
    test_map = {
        'precinctname': 'PrecinctName',
        'party': 'Party',
        'turnout_current': 'General24',
        'city': 'mCity'
    }
    print(run_pipeline(column_map=test_map))
