import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("venv/Lib/site-packages"))

from main import load_inputs, find_voter_geo_columns, build_voter_flags, to_clean_district_str

def inspect():
    inputs = load_inputs(allow_mock=False)
    voter_df = inputs['voters']
    geo_cols = find_voter_geo_columns(voter_df)
    geo_cols_lower = {k: v.lower() if v else None for k, v in geo_cols.items()}
    voter_flags = build_voter_flags(voter_df, inputs['has_prior_turnout'], geo_cols_lower)
    
    agg_prec = voter_flags.groupby('PrecinctName').agg({
        'PrecinctName': 'count'
    }).rename(columns={'PrecinctName': 'Total_Voters'}).reset_index()
    
    resolved_rows = []
    for idx, row in agg_prec.iterrows():
        p_name = row['PrecinctName']
        p_voters = voter_flags[voter_flags['PrecinctName'] == p_name]
        p_resolved = {'PrecinctName': p_name}
        
        v_col = geo_cols.get('supervisorial')
        val = None
        if v_col and v_col in p_voters.columns:
            mode_val = p_voters[v_col].dropna().mode()
            if not mode_val.empty:
                val = mode_val.iloc[0]
        p_resolved['Supervisorial_District'] = to_clean_district_str(val)
        resolved_rows.append(p_resolved)
        
    base_df = pd.DataFrame(resolved_rows)
    print("Columns:", list(base_df.columns))
    print("Unique Supervisorial_District:", base_df['Supervisorial_District'].dropna().unique())

if __name__ == "__main__":
    inspect()
