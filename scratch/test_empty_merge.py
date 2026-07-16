import pandas as pd
import numpy as np

df1 = pd.DataFrame(columns=["PrecinctName", "Val1"])
df2 = pd.DataFrame([{"PrecinctName": "A", "Val2": 10}, {"PrecinctName": "B", "Val2": 20}])

res = pd.merge(df1, df2[['PrecinctName', 'Val2']], on='PrecinctName', how='left')
print("res columns:", list(res.columns))
print("res empty:", res.empty)
