import os
import datetime
import pandas as pd
import logging

def generate_diagnostic_outputs(outputs_dir, state_dict):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(outputs_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    voter_flags = state_dict.get('voter_flags', pd.DataFrame())
    mprec_agg = state_dict.get('mprec_agg', pd.DataFrame())
    unmatched_mprec = state_dict.get('unmatched_mprec', pd.DataFrame())
    srprec_agg = state_dict.get('srprec_agg', pd.DataFrame())
    base_df = state_dict.get('base_df', pd.DataFrame())
    score_df = state_dict.get('score_df', pd.DataFrame())
    top_precincts = state_dict.get('top_precincts', pd.DataFrame())
    join_diagnostics = state_dict.get('join_diagnostics', pd.DataFrame())
    pipeline_warnings = state_dict.get('pipeline_warnings', [])
    weights = state_dict.get('weights', {})
    target_params = state_dict.get('target_params', {})
    
    # 01
    try:
        sample_cols = ['MPREC', 'Party_Clean', 'Voted_2024_Flag', 'Voted_Prior_Flag', 'Dem_Flag', 'Rep_Flag', 'NPP_Flag']
        available_cols = [c for c in sample_cols if c in voter_flags.columns]
        voter_flags[available_cols].head(1000).to_csv(os.path.join(run_dir, "01_voter_flag_sample.csv"), index=False)
    except: pass

    # 02
    try: mprec_agg.to_csv(os.path.join(run_dir, "02_mprec_aggregation.csv"), index=False)
    except: pass

    # 03
    try:
        if not unmatched_mprec.empty: unmatched_mprec.to_csv(os.path.join(run_dir, "03_unmatched_mprec.csv"), index=False)
    except: pass

    # 04
    try: srprec_agg.to_csv(os.path.join(run_dir, "04_srprec_aggregation.csv"), index=False)
    except: pass

    # 05
    try:
        d_cols = [c for c in base_df.columns if c in ['SRPREC', 'CITY', 'Assembly_District', 'Supervisorial_District', 'Area_Sq_Miles']]
        base_df[d_cols].to_csv(os.path.join(run_dir, "05_srprec_with_districts.csv"), index=False)
    except: pass

    # 07
    try:
        s_cols = ['SRPREC', 'CITY', 'Assembly_District', 'Supervisorial_District', 'Total_Voters', 
                  'Voted_Current', 'Turnout_Dropoff_Rate', 'Dem', 'Rep', 'NPP', 'Dem_Share', 'Competitive_Index', 
                  'Area_Sq_Miles', 'True_Density', 'Normalized_Turnout_Drop', 'Normalized_Competitive_Index', 
                  'Normalized_True_Density', 'Used_Density', 'Used_Underperformance', 'Priority_Score', 'Rank']
        s_cols = [c for c in s_cols if c in score_df.columns]
        score_df[s_cols].to_csv(os.path.join(run_dir, "07_scoring_breakdown.csv"), index=False)
    except Exception as e: logging.error(e)

    # 08
    try:
        if not score_df.empty:
            score_df.sort_values("Priority_Score", ascending=False).head(50).to_csv(os.path.join(run_dir, "08_top_50_precincts.csv"), index=False)
    except: pass

    # 09 (Dynamically parameterized naming instead of hardcoded)
    try:
        top_precincts.to_csv(os.path.join(run_dir, "09_target_overlap.csv"), index=False)
    except: pass

    # 11
    try:
        if not join_diagnostics.empty:
            join_diagnostics.to_csv(os.path.join(run_dir, "11_join_diagnostics.csv"), index=False)
    except: pass

    # 10
    try:
        summary_path = os.path.join(run_dir, "10_pipeline_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("PIPELINE AUDIT SUMMARY\n======================\n\n")
            
            f.write("DEPENDENCIES RESOLUTION:\n")
            f.write(f"Prior Turnout Available: {'YES' if score_df['Has_Prior_Turnout'].iloc[0] else 'NO (Density fallback)'}\n")
            f.write(f"Physical Map Area Available: {'YES' if score_df['Has_Area'].iloc[0] else 'NO (Area Density disabled)'}\n\n")

            f.write(f"TARGET PARAMETERS APPLIED: AD={target_params.get('ad')}, SD={target_params.get('sd')}, CITY={target_params.get('city')}\n\n")
            
            if pipeline_warnings:
                f.write("WARNINGS:\n")
                for w in pipeline_warnings: f.write(f"- {w}\n")
            else:
                f.write("WARNINGS: Clean\n")
                
        return summary_path
    except: return None
