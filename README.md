# Priority Precinct Generator (Beta)

A simple, local Python proof-of-concept pipeline for evaluating precinct priorities targeting Assembly District 12 and Supervisorial District 2 in Sonoma County.

## Setup

1. Make sure Python 3.9+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Expected Input Files

Place the following CSV files in the project root directory (or update the configuration in `main.py`):

- **voter_file.csv**: Raw voter data with these columns (minimum):
  - `PrecinctName` (treated as the MPREC)
  - `Party`
  - `General24`
  - `General22`
  - *(Optional)* `Primary24`, `Age`, `mCity`
- **mprec_srprec.csv**: Crosswalk file mapping Voter File Precincts (MPREC) to Master Precincts (SRPREC).
  - Requires `mprec` and `srprec` columns.
- **srprec_city.csv**: Mapping from SRPREC to California City.
  - Requires `srprec` and `city` columns.
- **district_assignment.csv**: Defines overlapping districts.
  - Requires `SRPREC`, `Assembly_District`, `Supervisorial_District` columns. If you do not have mapping data yet, use `district_assignment_template.csv` to create a blank or manually populated mapping.

## How to Run

Execute the main script:
```bash
python main.py
```

## Outputs Produced

The pipeline will create an `outputs` directory containing:

1. **precinct_targeting_workbook.xlsx**:
   The primary deliverable. It includes sheets: `Raw_Voter_Sample`, `Voter_With_Flags`, `MPREC_Aggregate`, `SRPREC_Aggregate`, `Precinct_Base`, `Scoring`, `Overlap_AD12_SD2`, and `QA_Checks`.
2. **CSV Artifacts**:
   - `outputs/mprec_aggregate.csv`
   - `outputs/srprec_aggregate.csv`
   - `outputs/precinct_base.csv`
   - `outputs/scoring.csv`
   - `outputs/overlap_ad12_sd2.csv`
   - `outputs/qa_checks.csv`
3. **QA Unmatched Data**:
   - `outputs/unmatched_mprec.csv`
   - `outputs/unmatched_srprec_city.csv`
   - `outputs/unmatched_srprec_district.csv`
4. **run.log**:
   Execution log containing row count analysis, loaded files, matching metrics, and diagnostic warnings.

## Overview of Scoring Logic

The `Priority_Score` evaluates precincts based on three normalized dimensions:

1. **Turnout Gap (45% weight)**: Reflects total number of registered voters who did *not* vote in 2024. Indicates maximum upside potential.
2. **Competitive Index (35% weight)**: A measure of the Democratic/voter balance. Precincts splitting votes close to 50/50 receive a higher score (1.0), while single-party dominant precincts rank lower (0.0).
3. **Voter Count (20% weight)**: Rewards larger precincts for efficiency in contacting more total targetable doors.

*See `score_precincts()` inside `main.py` for exact computation details.*
