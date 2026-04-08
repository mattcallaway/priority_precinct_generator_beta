# Priority Precinct Generator (Beta)

Welcome to the automated pipeline for the **Priority Precinct Generator**. This tool is designed to consume raw voter data and map it together with precinct geographies (specifically targeting Assembly District 12 and Supervisorial District 2) to help prioritize campaign organizing and field efforts.

This project uses local Python scripts, meaning all data is parsed directly on your computer securely with no web servers or databases required. **We have recently upgraded this tool with a beautifully simple, one-click Graphical User Interface (GUI) to replace the old terminal workflow!**

---

## 1. Prerequisites

Before you begin, you only need two things prepared:
1. **Python**: The programming language that runs the scripts in the background. You can download it for free from [python.org](https://www.python.org/downloads/). (Make sure to check the box that says "Add Python to PATH" during installation).
2. **Your Input Files**: You will need to export 4 CSV (comma-separated values) spreadsheets from your voter database and mapping resources. The exact column names required are displayed inside the application.

---

## 2. Running the Application

Forget typing terminal commands. To start the application, simply:

### **If you use Windows:**
Double-click the **`run_generator.bat`** file inside this folder.
*(The first time you run it, it might take a minute to download the required components. Afterwards, it will instantly launch.)*

### **If you use Mac/Linux:**
Double-click the **`run_generator.sh`** file.
*(Or run `bash run_generator.sh` from your terminal).*

A web page will magically open in your default browser perfectly formatted as a sleek dashboard.

---

## 3. Using the Dashboard

Once the app is open:
1. **Upload your files:** Simply drag and drop your `voter_file.csv`, `mprec_srprec.csv`, `srprec_city.csv`, and `district_assignment.csv` files directly onto the drop zones on the screen. The interface will tell you exactly which columns you need inside them.
2. **Adjust Weights (Optional):** Use the sliders on the left-hand sidebar if you wish to adjust the mathematical weights determining how much Turnout Gap, Competitiveness, or Voter Density impacts the final Priority Score.
3. **Generate Strategy:** Click the bold "Generate Strategy Dashboard" button.
4. **View & Download:** Wait just a few moments while the engine chunks through your big data. The screen will automatically refresh with your top precinct targets, QA diagnostic metrics, and a one-click button to download your final master `.xlsx` Workbook.

---

## What is in the Master Workbook?

| Tab Name | Purpose |
|----------|---------|
| **`Overlap_AD12_SD2`** | **Start here.** This tab contains only the precincts sitting squarely in both Assembly District 12 and Supervisorial District 2. They are pre-sorted from highest `Priority_Score` to lowest. These are the doors you want to knock first. |
| **`Scoring`** | The complete scoring breakdown for *every* mapped precinct in the entire county/source file, not just the overlap. |
| **`QA_Checks`** | A critical diagnostic tab. It tells you exactly how many voters were ingested and whether any relationships failed to map. |
| **`Raw_Voter_Sample`** | A tiny 500-voter sample of the source data so you can verify the participation/party flags applied correctly. |

---

### Did something go wrong?
If the unmatched mappings metric is high on your app screen, or a file crashes during upload, the most common issue is missing columns. Ensure that your raw data matches the column names requested inside the app *exactly* (spelling matters)! Any problematic outputs will still be saved inside your local `outputs/` folder.
