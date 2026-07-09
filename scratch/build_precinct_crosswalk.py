import os
import sys
sys.path.insert(0, os.path.abspath("."))
import re
import pandas as pd
import numpy as np
import pypdf

def clean_voter_precinct(p):
    if pd.isna(p):
        return ""
    p_str = str(p).strip()
    if p_str.endswith(".0"):
        p_str = p_str[:-2]
    # If it is purely numeric, zfill to 7
    if p_str.isdigit():
        return p_str.zfill(7)
    return p_str

def parse_pdf(path, name):
    reader = pypdf.PdfReader(path)
    rows = []
    
    for page_idx, page in enumerate(reader.pages):
        text = page.extract_text()
        for line_idx, line in enumerate(text.split('\n')):
            line = line.strip()
            if not line:
                continue
            tokens = line.split()
            if 'PCT' not in tokens:
                continue
                
            # If full line containing '-'
            if '-' in tokens:
                idx = tokens.index('-')
                before = tokens[:idx]
                if len(before) == 2:
                    ballot_type = before[0]
                    voting_prec = before[1]
                elif len(before) == 1:
                    tok = before[0]
                    ballot_type = tok[:-7]
                    voting_prec = tok[-7:]
                else:
                    continue
                after = tokens[idx+1:]
                if len(after) >= 6:
                    vbm_prec = after[2]
                    reg_prec = after[3]
                    rows.append({
                        'Regular_Precinct_Raw': reg_prec,
                        'Regular_Precinct_Normalized': reg_prec,
                        'VBM_Precinct_Raw': vbm_prec,
                        'VBM_Precinct_Normalized': vbm_prec,
                        'Voting_Precinct_Raw': voting_prec,
                        'Voting_Precinct_Normalized': voting_prec,
                        'Ballot_Type': ballot_type,
                        'Source_File': name,
                        'Source_Page': page_idx + 1,
                        'Parse_Status': 'SUCCESS'
                    })
            else:
                # Continuation line
                # [ vbm_plus_ballot, reg_prec, 'PCT', reg_prec_norm ]
                # e.g. ['14710001', '0100002', 'PCT', '0100002']
                if len(tokens) >= 4 and tokens[2] == 'PCT':
                    tok = tokens[0]
                    ballot_type = tok[:-7]
                    vbm_prec = tok[-7:]
                    voting_prec = '0' + vbm_prec[1:]
                    reg_prec = tokens[1]
                    rows.append({
                        'Regular_Precinct_Raw': reg_prec,
                        'Regular_Precinct_Normalized': reg_prec,
                        'VBM_Precinct_Raw': vbm_prec,
                        'VBM_Precinct_Normalized': vbm_prec,
                        'Voting_Precinct_Raw': voting_prec,
                        'Voting_Precinct_Normalized': voting_prec,
                        'Ballot_Type': ballot_type,
                        'Source_File': name,
                        'Source_Page': page_idx + 1,
                        'Parse_Status': 'SUCCESS'
                    })
    return pd.DataFrame(rows)

def build_canonical_crosswalk():
    os.makedirs("outputs/precinct_crosswalk", exist_ok=True)
    
    print("Parsing Regular to Voting PDF (ewmr010)...")
    df_reg_to_voting = parse_pdf(r"D:\Downloads\ewmr010_regabsvotpctxref_2026-06-02.pdf", "ewmr010_regabsvotpctxref_2026-06-02.pdf")
    df_reg_to_voting.to_csv(r"outputs\precinct_crosswalk\parsed_regular_vbm_voting_xref.csv", index=False)
    
    print("Parsing Voting to Regular PDF (ewmr008)...")
    df_voting_to_reg = parse_pdf(r"D:\Downloads\ewmr008_votabsregpctxref_2026-06-02.pdf", "ewmr008_votabsregpctxref_2026-06-02.pdf")
    df_voting_to_reg.to_csv(r"outputs\precinct_crosswalk\parsed_voting_vbm_regular_xref.csv", index=False)
    
    print("Parsing complete. Row counts:", len(df_reg_to_voting), len(df_voting_to_reg))
    
    # Load SOV to verify presence
    print("Loading SOV detail.csv...")
    df_det = pd.read_csv("data/detail.csv", header=None)
    # The header is actually on row 1 or we can use inspect_and_load_file logic.
    # To keep it simple, let's load using inspect_and_load_file via import
    from contest_manager import inspect_and_load_file
    sov_res = inspect_and_load_file("data/detail.csv")
    df_det_clean = sov_res["df"]
    sov_precs = set(df_det_clean["Precinct"].dropna().astype(str).unique())
    
    # Load Voter file to find unique PrecinctNames
    print("Loading voter_file.csv...")
    df_vot = pd.read_csv("data/voter_file.csv")
    voter_precs = set(df_vot["PrecinctName"].dropna().astype(str).unique())
    
    # Map voter precincts to cleaned, padded formats
    voter_map = {}
    for vp in voter_precs:
        vp_clean = clean_voter_precinct(vp)
        if vp_clean:
            voter_map[vp_clean] = vp
            
    # Compile canonical crosswalk using the unique relationships from the parsed tables
    # Combine unique mappings from both files
    all_mappings = pd.concat([df_reg_to_voting, df_voting_to_reg]).drop_duplicates(
        subset=["Regular_Precinct_Normalized", "Voting_Precinct_Normalized", "VBM_Precinct_Normalized", "Ballot_Type"]
    )
    
    # Count mappings per Voting Precinct to determine One_To_Many flag
    voting_counts = all_mappings["Voting_Precinct_Normalized"].value_counts().to_dict()
    # Count mappings per Regular Precinct to determine Many_To_One flag
    reg_counts = all_mappings["Regular_Precinct_Normalized"].value_counts().to_dict()
    
    canonical_rows = []
    
    for idx, row in all_mappings.iterrows():
        reg_norm = row["Regular_Precinct_Normalized"]
        voting_norm = row["Voting_Precinct_Normalized"]
        vbm_norm = row["VBM_Precinct_Normalized"]
        ballot_type = row["Ballot_Type"]
        
        # Check if it connects to voter file
        voter_prec_name = voter_map.get(reg_norm, np.nan)
        voter_file_connected = pd.notna(voter_prec_name)
        
        # Check if Voting Precinct is in SOV
        sov_prec_raw = np.nan
        sov_prec_normalized = np.nan
        sov_connected = False
        
        for sp in sov_precs:
            if sp.strip() == voting_norm or sp.strip().lstrip('0') == voting_norm.lstrip('0'):
                sov_prec_raw = sp
                sov_prec_normalized = voting_norm
                sov_connected = True
                break
                
        # Determine Match Rule
        if reg_norm == voting_norm:
            match_rule = "exact_match"
        else:
            match_rule = "official_crosswalk_inherited"
            
        one_to_many = "YES" if voting_counts.get(voting_norm, 0) > 1 else "NO"
        many_to_one = "YES" if reg_counts.get(reg_norm, 0) > 1 else "NO"
        
        # Validation rules:
        valid_for_production = "FALSE"
        notes = "Crosswalk record parsed successfully."
        
        if voter_file_connected and sov_connected:
            valid_for_production = "TRUE"
            notes = "Valid production bridge established: SOV Voting Precinct -> Regular Precinct -> Voter PrecinctName."
        elif not voter_file_connected:
            notes = "Regular precinct code not found in campaign voter file."
        elif not sov_connected:
            notes = "Voting precinct not present in Statement of Votes file."
            
        canonical_rows.append({
            "Election_ID": "2026-06-02",
            "County": "Sonoma",
            "Contest_Name": "Supervisor D4 Melanie Bagby vs Tom Schwedhelm",
            "SOV_Precinct_Raw": sov_prec_raw,
            "SOV_Precinct_Normalized": sov_prec_normalized,
            "Voting_Precinct": voting_norm,
            "VBM_Precinct": vbm_norm,
            "Regular_Precinct": reg_norm,
            "Voter_PrecinctName": voter_prec_name,
            "Ballot_Type": ballot_type,
            "Match_Rule": match_rule,
            "Match_Source": "official_sonoma_rov_cross_reference",
            "Match_Confidence": "high",
            "One_To_Many_Flag": one_to_many,
            "Many_To_One_Flag": many_to_one,
            "Valid_For_Production": valid_for_production,
            "Notes": notes
        })
        
    df_canonical = pd.DataFrame(canonical_rows)
    df_canonical.to_csv(r"outputs\precinct_crosswalk\canonical_sov_to_voter_precinct_crosswalk.csv", index=False)
    print("Canonical crosswalk saved to outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk.csv")
    print("Valid for production count:", len(df_canonical[df_canonical["Valid_For_Production"] == "TRUE"]))

if __name__ == "__main__":
    build_canonical_crosswalk()
