import sys
sys.path.insert(0, ".")
import pandas as pd
from main import find_voter_geo_columns, to_clean_district_str
import os

voter_df = pd.read_csv("data/voter_file.csv", nrows=100)
geo_cols = find_voter_geo_columns(voter_df)
print("Geo cols:", geo_cols)

sds = voter_df[geo_cols['supervisorial']].dropna().unique().tolist()
print("Raw sds:", sds)
sd_opts = sorted(list(set([to_clean_district_str(x) for x in sds if to_clean_district_str(x) != 'Unmapped'])))
print("sd_opts:", sd_opts)
