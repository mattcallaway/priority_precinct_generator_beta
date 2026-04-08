import pandas as pd
import numpy as np
import os

def create_mock_data():
    os.makedirs('data', exist_ok=True)
    
    print("Generating mock data...")
    # 1. Voter File
    np.random.seed(42)
    n_voters = 1000
    mprecs = [f"MPREC_{i:03d}" for i in range(1, 21)]
    parties = ["DEM", "REP", "NPP", "Green", "Libertarian", "American Independent"]
    parties_weights = [0.45, 0.25, 0.20, 0.03, 0.03, 0.04]
    
    voter_data = {
        "PrecinctName": np.random.choice(mprecs, n_voters),
        "Party": np.random.choice(parties, n_voters, p=parties_weights),
        "General24": np.random.choice(["Y", "", "A", "V"], n_voters, p=[0.6, 0.3, 0.05, 0.05]),
        "General22": np.random.choice(["Y", "", "A", "V"], n_voters, p=[0.5, 0.4, 0.05, 0.05]),
        "Primary24": np.random.choice(["Y", ""], n_voters, p=[0.4, 0.6]),
        "Age": np.random.randint(18, 90, n_voters),
        "mCity": np.random.choice(["Santa Rosa", "Petaluma"], n_voters)
    }
    pd.DataFrame(voter_data).to_csv('data/voter_file.csv', index=False)
    
    # 2. MPREC to SRPREC
    srprecs = [f"SRPREC_{i:03d}" for i in range(1, 11)]
    mprec_mapping = {"mprec": mprecs[:-2], "srprec": np.random.choice(srprecs, len(mprecs)-2)}
    pd.DataFrame(mprec_mapping).to_csv('data/mprec_srprec.csv', index=False)
    
    # 3. SRPREC to CITY
    cities = ["Santa Rosa", "Petaluma", "Sonoma"]
    srprec_city_mapping = {"srprec": srprecs[:-1], "city": np.random.choice(cities, len(srprecs)-1)}
    pd.DataFrame(srprec_city_mapping).to_csv('data/srprec_city.csv', index=False)
    
    # 4. District Assignment
    # Set a couple to definitely be AD 12 and SD 2
    ad = np.random.choice([12, 10, 2], len(srprecs))
    sd = np.random.choice([2, 1, 3, 4, 5], len(srprecs))
    ad[0] = 12
    sd[0] = 2
    ad[1] = 12
    sd[1] = 2
    districts = {"SRPREC": srprecs, 
                 "Assembly_District": ad,
                 "Supervisorial_District": sd}
    pd.DataFrame(districts).to_csv('data/district_assignment.csv', index=False)
    print("Mock data generated in 'data' directory.")

if __name__ == "__main__":
    create_mock_data()
