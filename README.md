# Priority Precinct Generator (Beta)

Welcome to the automated pipeline for the **Priority Precinct Generator**. This is a standalone tool designed to consume raw voter data and map it together with precinct geographies (specifically targeting Assembly District 12 and Supervisorial District 2) to help prioritize campaign organizing and field efforts.

This project uses local Python scripts, meaning all data is parsed directly on your computer securely with no web servers or databases required.

## 1. Prerequisites (What you need on your computer)

Before you begin, you only need two things installed on your computer:
1. **Python**: The programming language that runs the scripts. You can download it for free from [python.org](https://www.python.org/downloads/). (Make sure to check the box that says "Add Python to PATH" during installation).
2. **Your Input Files**: You will need to export 3 to 4 CSV (comma-separated values) spreadsheets from your voter database and mapping resources.

---

## 2. Preparing Your Input Data

The script works by looking for a folder named `data` and reading your CSV files from it. 

### Step 2a: Create the Data Folder
1. Open the project folder (`priority_precinct_generator_beta`).
2. Inside that folder, create a new empty folder and name it exactly: `data`

### Step 2b: Prepare and Rename Your Files
You need to place real CSV files into that `data` folder. The script has been programmed to look for specific file names. Rename your downloaded files to match these **exactly**:

1. **`voter_file.csv`**
   - **What it is:** The raw list of registered voters.
   - **Required Columns:** It *must* have columns named `PrecinctName`, `Party`, `General24`, and `General22`. (It's okay if it has additional columns like `mCity` or `Age`). The script is smart enough to handle capitalization differences (e.g., `precinctname` vs. `PrecinctName`).

2. **`mprec_srprec.csv`**
   - **What it is:** The crosswalk file linking your Voter File Precincts (MPREC) to the Master Precinct Boundaries (SRPREC).
   - **Required Columns:** It *must* have columns `mprec` and `srprec`. 

3. **`srprec_city.csv`**
   - **What it is:** A mapping file tying the Master Precinct Boundaries (SRPREC) to the city name (e.g., Santa Rosa, Petaluma, etc.).
   - **Required Columns:** It *must* have columns `srprec` and `city`.

4. **`district_assignment.csv`**
   - **What it is:** A map of overlapping districts to determine who belongs to Assembly District 12 and Superisorial District 2. 
   - **Required Columns:** It *must* have columns `SRPREC`, `Assembly_District`, and `Supervisorial_District`.
   - *Note:* If you do not have this file, there is a blank template provided in the project called `district_assignment_template.csv`. You can open it in Excel, manually fill in your SRPREC numbers and their corresponding districts, rename it `district_assignment.csv`, and place it in the `data` folder.

**CRITICAL WARNING:** 
If you misspell these file names (e.g., `voter-file.csv` instead of `voter_file.csv`), the script will not be able to find your data and will throw an error immediately telling you so.

---

## 3. Running the Pipeline

Once your files are securely in the `data` folder, executing the tool takes just seconds.

### Step 3a: Open your Command Prompt / Terminal
- On Windows: Press `Win + R`, type `cmd`, and press Enter.
- On Mac: Open Spotlight (`Cmd + Space`), type `Terminal`, and press Enter.

### Step 3b: Navigate to the Project Folder
Use the `cd` (change directory) command to point your terminal to the project folder. For example:
```bash
cd Documents/priority_precinct_generator_beta
```

### Step 3c: (First Time Only) Setup the Code
The very first time you use the tool on a computer, you must tell Python to download the required spreadsheet tools (`pandas` and `openpyxl`). Type this and press enter:
```bash
python -m pip install -r requirements.txt
```

### Step 3d: Run the Generator
To crunch the data, type this single command and press Enter:
```bash
python main.py
```
You will immediately see text output in your console confirming that it is reading your files, matching the geography, scoring the precincts, and generating your Excel workbook!

---

## 4. Reading the Outputs

When the script finishes, a new folder will magically appear in your project folder called `outputs`. Inside it, you will find your master deliverable: **`precinct_targeting_workbook.xlsx`** (along with raw `.csv` versions of every sheet for portability).

### Important Tabs in your Excel Workbook:

| Tab Name | Purpose |
|----------|---------|
| **`Overlap_AD12_SD2`** | **Start here.** This tab contains only the precincts sitting squarely in both Assembly District 12 and Supervisorial District 2. They are pre-sorted from highest `Priority_Score` to lowest. These are the doors you want to knock first. |
| **`Scoring`** | The complete scoring breakdown for *every* mapped precinct in the entire county/source file, not just the overlap. |
| **`QA_Checks`** | A critical diagnostic tab. It tells you exactly how many voters were ingested and whether any MPREC/SRPREC relationships failed to map. |
| **`Raw_Voter_Sample`** | A tiny 500-voter sample of the source data so you can verify the participation/party flags applied correctly. |

### How is the Priority Score Calculated?
The `Priority_Score` ranks your precincts on three criteria. Higher scores are always better:
- **45% - Turnout Gap:** We favor precincts with high numbers of non-voters (e.g. they missed 2024). They represent the highest upside.
- **35% - Competitive Index:** We favor "toss-up" precincts that split 50/50 over heavily homogenous single-party districts where turnout impacts the ultimate margin less significantly.
- **20% - Voter Density:** We favor larger precincts natively, maximizing the raw number of targetable voters on a single block to reduce transit times for canvassers.

### Did something go wrong?
If the numbers look bizarre, look inside the `outputs/` folder for three special `.csv` files:
- `unmatched_mprec.csv`
- `unmatched_srprec_city.csv`
- `unmatched_srprec_district.csv`

If there are rows in these files, it signifies mapping blind spots (i.e. a voter lived in an MPREC that simply didn't exist in your crosswalk file linking it to an SRPREC). You can update your raw data and run the script over again anytime.
