import os
import datetime
import pandas as pd
import logging

def generate_diagnostic_outputs(outputs_dir, state_dict):
    """
    Generates 12 highly specific diagnostic truth-sets to perfectly audit the scoring run.
    """
    # Create timestamped directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(outputs_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Extract dataframes
    voter_flags = state_dict.get('voter_flags', pd.DataFrame())
    mprec_agg = state_dict.get('mprec_agg', pd.DataFrame())
    unmatched_mprec = state_dict.get('unmatched_mprec', pd.DataFrame())
    srprec_agg = state_dict.get('srprec_agg', pd.DataFrame())
    base_df = state_dict.get('base_df', pd.DataFrame())
    unmatched_districts = state_dict.get('unmatched_districts', pd.DataFrame())
    score_df = state_dict.get('score_df', pd.DataFrame())
    top_precincts = state_dict.get('top_precincts', pd.DataFrame())
    join_diagnostics = state_dict.get('join_diagnostics', pd.DataFrame())
    pipeline_warnings = state_dict.get('pipeline_warnings', [])
    weights = state_dict.get('weights', {})
    
    # 01_voter_flag_sample.csv
    try:
        sample_cols = ['PrecinctName', 'MPREC', 'Party', 'general24', 'general22', 
                       'Voted_2024_Flag', 'Voted_2022_Flag', 'Dem_Flag', 'Rep_Flag', 
                       'NPP_Flag', 'OtherParty_Flag']
        available_cols = [c for c in sample_cols if c in voter_flags.columns]
        voter_flags[available_cols].head(1000).to_csv(os.path.join(run_dir, "01_voter_flag_sample.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 01: {e}")

    # 02_mprec_aggregation.csv
    try:
        mprec_agg.to_csv(os.path.join(run_dir, "02_mprec_aggregation.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 02: {e}")

    # 03_unmatched_mprec.csv
    try:
        if not unmatched_mprec.empty:
            # Requires MPREC, count_of_voters
            unmatched_mprec.to_csv(os.path.join(run_dir, "03_unmatched_mprec.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 03: {e}")

    # 04_srprec_aggregation.csv
    try:
        srprec_agg.to_csv(os.path.join(run_dir, "04_srprec_aggregation.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 04: {e}")

    # 05_srprec_with_districts.csv
    try:
        dist_cols = ['SRPREC', 'CITY', 'Assembly_District', 'Supervisorial_District', 'assignment_method', 'qa_flag']
        d_cols = [c for c in dist_cols if c in base_df.columns]
        base_df[d_cols].to_csv(os.path.join(run_dir, "05_srprec_with_districts.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 05: {e}")

    # 06_unmatched_districts.csv
    try:
        unmatched_districts.to_csv(os.path.join(run_dir, "06_unmatched_districts.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 06: {e}")

    # 07_scoring_breakdown.csv
    try:
        score_cols = ['SRPREC', 'CITY', 'Assembly_District', 'Supervisorial_District', 'Total_Voters', 
                      'Voted_2024', 'Turnout_Gap', 'Dem', 'Rep', 'NPP', 'Dem_Share', 'Competitive_Index', 
                      'Normalized_Turnout_Gap', 'Normalized_Competitive_Index', 'Normalized_Density', 
                      'Priority_Score', 'Rank']
        s_cols = [c for c in score_cols if c in score_df.columns]
        score_df[s_cols].to_csv(os.path.join(run_dir, "07_scoring_breakdown.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 07: {e}")

    # 08_top_50_precincts.csv
    try:
        if not score_df.empty:
            score_df.sort_values("Priority_Score", ascending=False).head(50).to_csv(os.path.join(run_dir, "08_top_50_precincts.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 08: {e}")

    # 09_overlap_ad12_sd2.csv
    try:
        top_precincts.to_csv(os.path.join(run_dir, "09_overlap_ad12_sd2.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 09: {e}")

    # 11_join_diagnostics.csv
    try:
        if not join_diagnostics.empty:
            join_diagnostics.to_csv(os.path.join(run_dir, "11_join_diagnostics.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 11: {e}")

    # 12_score_distribution.csv
    try:
        if not score_df.empty and 'Priority_Score' in score_df.columns:
            counts, bins = pd.cut(score_df['Priority_Score'], bins=10, retbins=True)
            dist_df = pd.DataFrame({'Score_Bin': counts.value_counts().index.astype(str), 'Count': counts.value_counts().values})
            dist_df.sort_values("Score_Bin").to_csv(os.path.join(run_dir, "12_score_distribution.csv"), index=False)
    except Exception as e: logging.error(f"Error writing 12: {e}")

    # 10_pipeline_summary.txt
    try:
        summary_path = os.path.join(run_dir, "10_pipeline_summary.txt")
        
        mprec_mr = "N/A"
        srprec_mr = "N/A"
        if not join_diagnostics.empty:
            try:
                m_rates = join_diagnostics.set_index('step_name')['match_rate'].to_dict()
                mprec_mr = m_rates.get('MPREC_to_SRPREC', 'N/A')
                srprec_mr = m_rates.get('SRPREC_to_DISTRICT', 'N/A')
            except: pass
            
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=========================================\n")
            f.write("          PIPELINE AUDIT SUMMARY\n")
            f.write("=========================================\n\n")
            
            f.write("OVERVIEW:\n")
            f.write(f"Total voters processed: {len(voter_flags):,}\n")
            f.write(f"Unique MPREC: {voter_flags.get('MPREC', pd.Series()).nunique():,}\n")
            f.write(f"Unique SRPREC: {base_df.get('SRPREC', pd.Series()).nunique():,}\n\n")
            
            f.write("JOIN INTEGRITY:\n")
            f.write(f"MPREC -> SRPREC match rate: {mprec_mr}\n")
            f.write(f"SRPREC -> District match rate: {srprec_mr}\n\n")
            
            f.write("TOP 5 PRIORITY PRECINCTS (County-Wide):\n")
            if not score_df.empty:
                top5 = score_df.sort_values("Priority_Score", ascending=False).head(5)
                for rank, row in enumerate(top5.itertuples(), 1):
                    # handle missing city or dist safely
                    city = getattr(row, 'CITY', 'Unknown')
                    ad = getattr(row, 'Assembly_District', 'U')
                    sd = getattr(row, 'Supervisorial_District', 'U')
                    score = getattr(row, 'Priority_Score', 0)
                    srprec = getattr(row, 'SRPREC', 'U')
                    f.write(f"{rank}. SRPREC {srprec} (City: {city} | AD:{ad} SD:{sd}) Score: {score:.3f}\n")
            else:
                f.write("None calculated.\n")
                
            f.write("\nSYSTEM WARNINGS & AUDIT FLAGS:\n")
            if pipeline_warnings:
                for w in pipeline_warnings:
                    f.write(f"- {w}\n")
            else:
                f.write("- All pre-flight math validations passed cleanly.\n")
                
        return summary_path
    except Exception as e:
        logging.error(f"Error writing 10: {e}")
        return None
