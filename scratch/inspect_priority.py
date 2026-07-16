import pandas as pd
import numpy as np

df = pd.read_csv("outputs/final_rankings/production_priority_precincts.csv")
print("Total rows:", len(df))
print("Contest_Result_Is_Inherited values:")
print(df["Contest_Result_Is_Inherited"].value_counts(dropna=False))

inherited = df[df["Contest_Result_Is_Inherited"] == True]
print("\nInherited rows sample (first 5):")
print(inherited[["PrecinctName", "Contest_Result_Is_Inherited", "Official_Parent_SOV_Total_Votes", "Contest_Total_Votes", "Contest_Enrichment_Source"]].head(5))

print("\nExact match rows sample (first 5):")
exact = df[df["Contest_Result_Is_Inherited"] == False]
print(exact[["PrecinctName", "Contest_Result_Is_Inherited", "Official_Parent_SOV_Total_Votes", "Contest_Total_Votes", "Contest_Enrichment_Source"]].head(5))

print("\nOfficial_Parent_SOV_Total_Votes non-null count:", df["Official_Parent_SOV_Total_Votes"].notna().sum())
print("Contest_Total_Votes non-null count:", df["Contest_Total_Votes"].notna().sum())
