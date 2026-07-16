import pandas as pd
df = pd.DataFrame()
df["Countywide_Base_Priority_Score"] = pd.Series(dtype=float)
df["Countywide_Base_Rank"] = pd.Series(dtype=float)
print("df columns:", list(df.columns))
