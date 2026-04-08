# Priority Precinct Engine: Master Technical Blueprint

This document constitutes the exhaustive technical and theoretical roadmap for the **Priority Precinct Generator (Beta)**. It is meticulously designed for system architects, data directors, and QA teams to identify exactly how fragmented raw campaign signals are digested, validated, and computed into a single, tactical door-knocking priority score.

There are zero "black boxes" in this pipeline. The design philosophy strictly demands that every action, aggregate, and mathematical normalization must generate an explicit verification file for auditing.

---

## 🧭 Full System Architecture Diagram

```mermaid
graph TD
    %% Base Interface Layer
    subgraph Streamlit Interface ["Front-End Session State (app.py)"]
        UI_T1[TAB 1: Core Uploads]
        UI_T2[TAB 2: City Mapping Manager]
        UI_T3[TAB 3: District Mapping Manager]
        UI_T4[TAB 4: Execution Engine]
        
        UI_S[Real-Time Validation Dashboard]
    end

    %% Storage Layer
    subgraph Data Intake ["Disk Ingestion (/data/)"]
        D1[voter_file.csv]
        D2[mprec_srprec.csv]
        
        CS[city_shapes.zip]
        C1[srprec_city.csv]
        
        AS[assembly_shapes.zip]
        SS[supervisorial_shapes.zip]
        D3[district_assignment.csv]
    end

    %% Geospatial Layer
    subgraph Geographic Processor ["Geospatial Builder (geo_processor.py)"]
        G1[Extract Representative Polygon Points]
        G2[Coordinate Harmonization: EPSG:3857]
        G3(City Polygons: Spatial Intersects)
        G4(District Polygons: Spatial Intersects)
        G5[Null Fallback Handler: Unincorporated]
    end

    %% Core Calculation Layer
    subgraph Analytics Engine ["Analytics Execution (main.py)"]
        A_Ingest[Validate Loaded Dataframes]
        A_Flags[Build 2022/2024 Base Voter Flags]
        A_AggM[Aggregate Voters into MPREC]
        A_Match[Join MPREC -> SRPREC Master Crosswalk]
        A_AggS[Aggregate MPREC clusters into SRPREC]
        A_JoinD[Left Join City & District Mapping Files]
        A_Score[Execute Priority Score Normalization]
    end

    %% The Audit Output Layer
    subgraph Diagnostic Generation ["Audit Output Subsystem (core_diagnostics.py)"]
        QA1[01: Voter Sample]
        QA2[02: MPREC Aggregate]
        QA3[03: Unmatched MPRECs]
        QA4[04: SRPREC Aggregate]
        QA5[05: SRPREC + Districts]
        QA6[06: Unmatched Districts]
        QA7[07: Scoring Bins]
        QA8[08: Top 50 Precision]
        QA9[09: Targeting Filter Overlap]
        QA10[10: Pipeline Audit Text Log]
        QA11[11: Join Match Rates]
        QA12[12: Score Bellcurve Distribution]
    end

    %% Relationships
    UI_T1 --> D1 & D2
    UI_T2 --> CS & C1
    UI_T3 --> AS & SS & D3
    
    CS --> Geographic Processor
    AS --> Geographic Processor
    SS --> Geographic Processor
    Geographic Processor -->|Autobuilds Missing CSVs| C1 & D3
    
    D1 & D2 & C1 & D3 -->|State Loaded| UI_S
    UI_S --> UI_T4
    UI_T4 --> Analytics Engine
    
    Analytics Engine --> Diagnostic Generation
```

---

## ⚙️ Module Breakdown & Responsibilities

The codebase relies on four decoupled components to segregate responsibilities and simplify debugging natively without cloud dependencies:

1. **`app.py` (The State Machine)**  
   - Handles the browser-based UI using Streamlit.
   - Constantly crawls the local `data/` volume to detect boolean configurations (does `voter_file.csv` exist? does `city_shapes.zip` exist?). 
   - Renders explicit GUI blockers if inputs are logically incomplete.

2. **`geo_processor.py` (The Cartographer)**  
   - Inherits pure Shapefiles using `geopandas` and `shapely`.
   - **Crucial Note:** Uses `.representative_point()` rather than `.centroid()`. Mathematical centroids can dangerously land *outside* of U-shaped or weirdly gerrymandered physical district boundaries. The representative point guarantees the mathematical X/Y falls strictly physically inside the border limits before executing `gpd.sjoin()`.
   - Bypasses manual ArcGIS/QGIS work by natively outputting standard mapping CSVs inside the environment.

3. **`main.py` (The Mathematical Engine)**  
   - The heart of the application. Transforms independent rows of raw voters into consolidated sub-precinct totals.
   - Carries out successive `pandas.merge(how='left')` structures so no data is silently dropped. If a join misses, it populates `NaN`, making it effortlessly identifiable for the `core_diagnostics` module.

4. **`core_diagnostics.py` (The Auditor)**  
   - Upon completion of `main.py`, the system drops a timestamped payload `outputs/run_YYMMDD_HHMMSS/` containing exactly 12 specific CSVs logging and exposing every micro-step of the matrix.

---

## 📐 Theory and Practice of the Targeting Math

The engine is engineered to find the **paths of least resistance with maximum localized upside**. Instead of sending campaigners explicitly to "where Democrats live" (an inefficient model in deep-blue saturated regions), it hunts for zones exhibiting massive reserves of *untapped, persuadable* turnout within heavily-populated blocks.

To prevent erratic numerical skewing, the `Priority Score` normalizes all variables down to a `Min-Max [0, 1.0]` scale. The worst precinct in the county gets a `0.0`, the strongest gets a `1.0`.

### Variable 1: Turnout Gap (Default Weight: 45%)
* **Campaign Theory:** High-turnout precincts are heavily saturated. Increasing margins there requires aggressive, expensive *persuasion* of entrenched voters. Conversely, precincts with massive gaps between overall registration and historical turnout offer enormous, cheaper *mobilization* upside. Let's aim the field program at dormant targets.
* **Math Execution:** 
  - `Raw Turnout Gap = Total Count of Precinct Voters - Count of Voters who cast a ballot in 2024`
  - Normalized: `(Precinct Gap - County Min Gap) / (County Max Gap - County Min Gap)`

### Variable 2: Competitive Index (Default Weight: 35%)
* **Campaign Theory:** Focusing on ultra-deep blue areas yields diminishing state-wide electoral returns. Instead, the tightest splits yield the highest value per single mobilized voter (since you are mobilizing an ally within an area where the opponent is attempting to mobilize theirs, creating a neutralizing defensive front).
* **Math Execution:** 
  - `Dem Share = Dem / (Dem + Rep + NPP + Other)`
  - `Deviation = |Dem Share - 0.50|` *(How far from a perfect tie is it?)*
  - `Index = 1 - (Deviation * 2)`
  - A mathematically tied `0.50` yields a `1.0`. A completely homogeneous `0.10` or `0.90` collapses toward `0.20`.

### Variable 3: Voter Density (Default Weight: 20%)
* **Campaign Theory:** Field organizing is a game of physics. Asking volunteers to commute between endless 10-acre rural parcels destroys canvasser morale and contact rates. We must bias toward thick neighborhood groupings.
* **Math Execution:** 
  - Direct normalization of the raw localized `Total_Voters` count.

> [!CAUTION]  
> **Diagnostic Flag Hooks**  
> The system tracks logic validation dynamically. If the math calculates that `Voted_2024 > Total_Voters` inside an aggregate block, or if the initial crosswalk mapping match-rate drops below 95%, `main.py` explicitly throws an audit flag visibly into `10_pipeline_summary.txt`. Always review the summary log to ensure the foundation beneath the math isn't critically fractured.
