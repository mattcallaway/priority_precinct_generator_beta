# Priority Precinct Generator (Beta)

Welcome to the automated pipeline for the **Priority Precinct Generator**. This tool evaluates raw campaign data alongside precinct-level geographies to identify exactly where your field program can achieve tactical advantages.

This project is entirely local, ensuring 100% data security. **It features a smart, highly-usable Drag-and-Drop Data Dashboard designed to ingest messy data, figure out what's missing, and help you automatically build missing logic maps via internal Geographic Information Systems (GIS) rendering.**

---

## 1. Prerequisites

1. **Python**: Required to run the background engine. Don't worry about being technical—just download it from [python.org](https://www.python.org/downloads/) and ensure you check "Add Python to PATH" during installation.
2. **Your Available Data**: Download what you have from your voter database. (You *no longer* need perfectly formatted outputs prior to running the app!)

---

## 2. Running the Application

Forget typing terminal commands. To start the application, simply:

### **If you use Windows:**
Double-click the **`run_generator.bat`** file inside this folder.
*(The first time you run it, it might take a minute to download the required mapping components like Geopandas. Afterwards, it will instantly launch.)*

### **If you use Mac/Linux:**
Double-click the **`run_generator.sh`** file.
*(Or run `bash run_generator.sh` from your terminal).*

A web page will magically open in your default browser perfectly formatted as a sleek dashboard.

---

## 3. Dynamic Workflow: Bring What You Have

The new Priority Precinct Generator is built around a **Flexible Input Matrix**. You do not need exactly 4 files to start. Instead:

### Step 1: Upload Baseline Inputs
Navigate to the "**1. Core Data Upload**" tab and drag any of the following into their specific drop-zones:
- `voter_file.csv`
- `mprec_srprec.csv` (Crosswalk)
- `srprec_city.csv` (City Mapping)

### Step 2: The Decision Engine
Check the top of your screen. The **Pipeline Status Panel** will constantly evaluate what it knows and what it is missing. Often, database exports do not strictly map out Legislative District allocations correctly.

If the app detects you are missing District information, navigate to "**2. District Mapping Manager**". You will have 3 options to solve the blank spot:
- **Option 1:** Upload a valid `district_assignment.csv` if another team member made one.
- **Option 2 (Geospatial Auto-Builder):** Upload standard zipped map Shapefiles boundaries (`srprec_shapes.zip`, `assembly_shapes.zip`, `supervisorial_shapes.zip`). The app will boot up an internal mapping engine, project every precinct onto the map, extract its centroid, and intersect it against your Assembly and Supervisorial lines in seconds, saving you hours of QGIS mapping overhead!
- **Option 3 (Template Generator):** Click the template button to have the app auto-generate an Excel worksheet perfectly formatted with your county's precincts pre-loaded into the columns, ready for you to manually tag.

### Step 3: Math Configuration & Execution
Once your status board reads green, navigate to "**3. Run & Results**".
Use the sliders on the left boundary to tell the math engine exactly what campaign theory to prioritize:
- **Turnout Gap:** Hunt for zones with high raw numbers of non-participating voters.
- **Competitive Index:** Hunt for heavily contested "toss up" zones.
- **Voter Density:** Hunt for massive neighborhood clusters to minimize canvasser walking time.

Click **Execute**, and the screen will output real-time QA diagnostics and grant you a Download button for the localized Master Workbook!

---

## What is in the Master Workbook?

| Tab Name | Purpose |
|----------|---------|
| **`Overlap_AD12_SD2`** | **Start here.** Pre-sorted priority targets explicitly overlapping your required Assembly and Supervisorial boundaries. |
| **`Scoring`** | The complete scoring breakdown for *every* mapped precinct in the entire county, regardless of targeted area. |
| **`QA_Checks`** | A critical diagnostic tab explaining how many sub-precinct relationships failed to map properly. |

### Technical Map & Math Theory
For deep mathematical transparency, your `outputs/` folder will generate a **`debug_explainer.txt`** alongside every run, detailing exactly how the priority score resolved. For a structural breakdown of the pipeline itself, please read `technical_map.md` in the master project folder.
