import json
import pandas as pd
import numpy as np

# Load voter file and SOV detail file
voter_file = "data/voter_file.csv"
sov_file = "data/detail.csv"

df_v = pd.read_csv(voter_file)
df_s = pd.read_csv(sov_file)

print("Voter file PrecinctNames first 5:")
print(df_v["PrecinctName"].head(5))

print("SOV columns:")
print(list(df_s.columns)[:10])


prec_col = "Precinct" if "Precinct" in df_s.columns else "PrecinctName" if "PrecinctName" in df_s.columns else "Precinct ID" if "Precinct ID" in df_s.columns else list(df_s.columns)[0]
print(f"Using precinct column: '{prec_col}'")

# Check zfilled padding in df_s
s_padded = df_s[prec_col].apply(lambda x: str(x).strip().zfill(7) if str(x).strip().isdigit() else str(x).strip().upper())
print("\nSOV file zfilled Precinct values (all non-null):")
non_null_sov = [x for x in s_padded.unique() if x not in ["NAN", "PRECINCT", "TOTAL", "GRAND TOTAL"]]
print(non_null_sov)



# Check crosswalk file
crosswalk_path = "outputs/precinct_crosswalk/canonical_sov_to_voter_precinct_crosswalk.csv"
df_c = pd.read_csv(crosswalk_path)
print("\nCrosswalk Voter_PrecinctName and Voting_Precinct first 5:")
print(df_c[["Voter_PrecinctName", "Voting_Precinct", "Valid_For_Production"]].head(5))

# Check unique mapped voting precincts in crosswalk
valid_c = df_c[df_c["Valid_For_Production"] == True]
print("\nUnique valid Voting_Precincts in crosswalk:")
print(valid_c["Voting_Precinct"].unique()[:10])

# Check intersection between crosswalk Voting_Precinct and SOV PREC_JOIN
sov_precs = set(s_padded.unique())
cross_precs = set(valid_c["Voting_Precinct"].astype(str).str.strip().str.upper().unique())
intersect = sov_precs.intersection(cross_precs)
print(f"\nSOV precincts: {len(sov_precs)}, Crosswalk valid voting precincts: {len(cross_precs)}, Intersection: {len(intersect)}")
print("Intersection sample:", list(intersect)[:5])
