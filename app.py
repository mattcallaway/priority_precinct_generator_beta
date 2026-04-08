import streamlit as st
import pandas as pd
import os
import shutil
import base64
from main import run_pipeline, generate_template

# Make sure geo_processor exists in the same folder and imports correctly
try:
    from geo_processor import generate_district_assignment_from_shapes, generate_city_assignment_from_shapes
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False

st.set_page_config(
    page_title="Priority Precinct Generator",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Styling ---
css = """
<style>
.stApp { background-color: #f8fafc; }
.metric-box { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); text-align: center; }
.metric-title { font-size: 14px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 32px; font-weight: bold; color: #0f172a; }
.status-box { background-color: white; padding: 15px; border-left: 5px solid #3b82f6; border-radius: 5px; margin-bottom: 20px;}
.hint-text { font-size: 13px; color: #6b7280; font-style: italic; margin-top: -10px; margin-bottom: 10px;}
</style>
"""
st.markdown(css, unsafe_allow_html=True)
os.makedirs("data", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

def save_uploaded(file_obj, filename):
    if file_obj is not None:
        with open(os.path.join("data", filename), "wb") as f:
            f.write(file_obj.getbuffer())

# --- PIPELINE STATUS REAL-TIME CHECKER ---
def check_status():
    status = {
        "voter": os.path.exists("data/voter_file.csv"),
        "mprec": os.path.exists("data/mprec_srprec.csv"),
        "city": os.path.exists("data/srprec_city.csv"),
        "dist": os.path.exists("data/district_assignment.csv"),
        
        # Geoprocessor detection
        "shp_srprec": os.path.exists("data/srprec_shapes.zip"),
        "shp_city": os.path.exists("data/city_shapes.zip"),
        "shp_assem": os.path.exists("data/assembly_shapes.zip"),
        "shp_sup": os.path.exists("data/supervisorial_shapes.zip")
    }
    status["dist_shapefiles_ready"] = status["shp_srprec"] and status["shp_assem"] and status["shp_sup"]
    status["city_shapefiles_ready"] = status["shp_srprec"] and status["shp_city"]
    status["ready_to_score"] = status["voter"] and status["mprec"] and status["city"] and status["dist"]
    return status

st.title("🗺️ Priority Precinct Generator (Beta)")
st.caption("Smart Pipeline: Upload what you have — we'll fill in the gaps.")

# --- SIDEBAR: Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    auto_gen = st.toggle("Auto-generate missing datasets", value=True, help="If data is missing but shapefiles exist, automatically build the required mapping files natively.")
    st.markdown("---")
    
    st.subheader("Priority Formula Weights")
    weight_turnout = st.slider("Turnout Dropoff", 0.0, 1.0, 0.45)
    weight_comp = st.slider("True Competitiveness", 0.0, 1.0, 0.35)
    weight_density = st.slider("Voter Volume", 0.0, 1.0, 0.20)
    
    tot = weight_turnout + weight_comp + weight_density
    if tot == 0: tot = 1; weight_turnout=0.33; weight_comp=0.33; weight_density=0.33
    weights = {"turnout_gap": weight_turnout/tot, "competitive_index": weight_comp/tot, "density": weight_density/tot}

# --- STATUS PANEL ---
status = check_status()
st.markdown('<div class="status-box">', unsafe_allow_html=True)
st.subheader("📊 Pipeline Status")
stat_cols = st.columns(4)
stat_cols[0].markdown(f"**Voter File:** {'✅ Loaded' if status['voter'] else '❌ Missing'}")
stat_cols[1].markdown(f"**Crosswalk:** {'✅ Loaded' if status['mprec'] else '❌ Missing'}")

# City Dynamic Status
if status['city']:
    stat_cols[2].markdown("**City Map:** ✅ Loaded")
elif status['city_shapefiles_ready']:
    stat_cols[2].markdown("**City Map:** 🟡 Ready to Generate")
else:
    stat_cols[2].markdown("**City Map:** ❌ Missing")

# District Dynamic Status
if status['dist']:
    stat_cols[3].markdown("**District Map:** ✅ Loaded")
elif status['dist_shapefiles_ready']:
    stat_cols[3].markdown("**District Map:** 🟡 Ready to Generate")
else:
    stat_cols[3].markdown("**District Map:** ❌ Missing")

if not status['ready_to_score']:
    st.warning("Action Needed: Please provide the missing files below to unlock the Scoring Pipeline.")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📁 1. Core Data Upload", 
    "🏙️ 2. City Mapping Manager", 
    "🗺️ 3. District Mapping Manager", 
    "🚀 4. Run & Results"
])

# --- TAB 1: CORE DATA ---
with tab1:
    st.markdown("### Upload Core Voter Files")
    st.info("💡 **File Sourcing Roadmap:** Grab these files directly from your central Voter Database (NGP VAN / PDI). You do NOT need mapping data yet.")
    
    c1, c2 = st.columns(2)
    
    with c1:
        voter_up = st.file_uploader("1. Voter File (`voter_file.csv`)", type=['csv'])
        st.markdown('<div class="hint-text">Source: Export your raw registered voter list directly from VAN/PDI.</div>', unsafe_allow_html=True)
        if voter_up: save_uploaded(voter_up, "voter_file.csv")
    
    with c2:
        mprec_up = st.file_uploader("2. MPREC Crosswalk (`mprec_srprec.csv`)", type=['csv'])
        st.markdown('<div class="hint-text">Source: Request the "Master to Subprecinct Crosswalk" list from your County Registrar of Voters (ROV).</div>', unsafe_allow_html=True)
        if mprec_up: save_uploaded(mprec_up, "mprec_srprec.csv")

    if st.button("Refresh Status", key="ref1"):
        st.rerun()

# --- TAB 2: CITY MAPPING MANAGER ---
with tab2:
    st.markdown("### City Assignment Manager")
    st.info("💡 **What is this?** This assigns a recognizable city to the precinct in the final sheet so volunteers know where they are driving.")
    
    if status['city']:
        st.success("✅ `srprec_city.csv` is already loaded into the system. You are good to go!")
        if st.button("🗑️ Remove City Mapping to start over"):
            os.remove("data/srprec_city.csv")
            st.rerun()
            
    else:
        opt1, opt2, opt3 = st.tabs(["Option 1: Upload Existing CSV", "Option 2: Generate via Shapefiles", "Option 3: Manual Entry Template"])
        
        with opt1:
            st.markdown("If you or a colleague already built a `.csv` with columns `srprec` and `city`, drop it here:")
            c_up = st.file_uploader("Upload CSV", type=['csv'], key="city_csv_up")
            if c_up:
                save_uploaded(c_up, "srprec_city.csv")
                st.success("Saved! Refesh the app.")
                if st.button("Refresh", key="ref_city"): st.rerun()
                
        with opt2:
            st.markdown("**Auto-Builder Roadmap:** We can automatically stamp the city name onto your precincts by smashing two map polygons together physically.")
            st.markdown('<div class="hint-text">Source: Download the City/Municipal Boundaries Shapefile from your Official County GIS Web Portal or the US Census Bureau TIGER line website. Always upload shapefiles as .zip archives!</div>', unsafe_allow_html=True)
            
            if not GEO_AVAILABLE:
                st.error("Missing Geopandas dependency.")
            else:
                sc1, sc2 = st.columns(2)
                shp_srprec = sc1.file_uploader("SRPREC Shapes (.zip)", type=['zip'], key="city_srp_up")
                shp_city = sc2.file_uploader("City/Municipal Shapes (.zip)", type=['zip'], key="city_shp_up")
                
                if shp_srprec: save_uploaded(shp_srprec, "srprec_shapes.zip")
                if shp_city: save_uploaded(shp_city, "city_shapes.zip")
                
                if st.button("🗺️ Generate City Mapping from Shapes", type="primary"):
                    if not (os.path.exists("data/srprec_shapes.zip") and os.path.exists("data/city_shapes.zip")):
                        st.error("Please upload both zip archives first.")
                    else:
                        with st.spinner("Crunching spatial matrices..."):
                            res = generate_city_assignment_from_shapes("data/srprec_shapes.zip", "data/city_shapes.zip", "data")
                            if res["status"] == "success": 
                                st.success(res['message'])
                                st.rerun()  # Hard reset to update status
                            else: st.error(res['message'])

        with opt3:
            st.write("Generate a blank Excel sheet pre-filled with all your unique sub-precincts. Type the city names in locally and upload it to Option 1.")
            if not status['mprec']:
                st.error("Upload the Core Crosswalk in Tab 1 first so we know what precincts to generate!")
            else:
                if st.button("📄 Generate City Excel Template"):
                    res = generate_template()
                    if res["status"] == "success":
                        st.success("Generated! Download below.")
                        with open(res["city_path"], "rb") as f:
                            st.download_button("Download Blank Template", data=f, file_name="srprec_city_template.csv", mime="text/csv")

# --- TAB 3: DISTRICT MAPPING MANAGER ---
with tab3:
    st.markdown("### Legislative District Manager")
    st.info("💡 **What is this?** A mapping file that routes precincts into specific Assembly and Supervisorial Districts.")
    
    if status['dist']:
        st.success("✅ `district_assignment.csv` is already loaded into the system.")
        if st.button("🗑️ Remove District file to start over"):
            os.remove("data/district_assignment.csv")
            st.rerun()
    else:
        opt1, opt2, opt3 = st.tabs(["Option 1: Upload Existing CSV", "Option 2: Generate via Shapefiles", "Option 3: Manual Entry Template"])
        
        with opt1:
            st.write("Upload a `.csv` with columns `SRPREC`, `assembly_district`, `supervisorial_district`.")
            d_up = st.file_uploader("Upload CSV", type=['csv'], key="dist_up")
            if d_up:
                save_uploaded(d_up, "district_assignment.csv")
                if st.button("Refresh", key="ref_dist"): st.rerun()
                
        with opt2:
            st.markdown("**Auto-Builder Roadmap:** Smash legislative boundaries against precincts to automatically assign districts.")
            st.markdown('<div class="hint-text">Source: Download the Assembly and Supervisorial Shapefiles from the official State Redistricting Commission or County GIS Open Data portal. Always upload shapefiles as .zip archives! (If you already uploaded the SRPREC zip in City Mapping, it will carry over automatically).</div>', unsafe_allow_html=True)
            
            if not GEO_AVAILABLE:
                st.error("Missing Geopandas dependency.")
            else:
                sc1, sc2, sc3 = st.columns(3)
                shp_srprec2 = sc1.file_uploader("SRPREC Shapes (.zip)", type=['zip'], key="dist_srp_up")
                shp_assem = sc2.file_uploader("Assembly Shapes (.zip)", type=['zip'], key="dist_assem_up")
                shp_sup = sc3.file_uploader("Supervisor Shapes (.zip)", type=['zip'], key="dist_sup_up")
                
                if shp_srprec2: save_uploaded(shp_srprec2, "srprec_shapes.zip")
                if shp_assem: save_uploaded(shp_assem, "assembly_shapes.zip")
                if shp_sup: save_uploaded(shp_sup, "supervisorial_shapes.zip")
                
                if st.button("🗺️ Generate Assignments from Shapes", use_container_width=True, type="primary", key="gendist"):
                    if not (os.path.exists("data/srprec_shapes.zip") and os.path.exists("data/assembly_shapes.zip") and os.path.exists("data/supervisorial_shapes.zip")):
                        st.error("Please ensure all 3 zip archives are provided.")
                    else:
                        with st.spinner("Crunching spatial matrices... (This can take a minute)"):
                            res = generate_district_assignment_from_shapes("data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data")
                            if res["status"] == "success": 
                                st.success(res['message'])
                                st.rerun()  # Hard reset to update status
                            else: st.error(res['message'])

        with opt3:
            st.write("Generate a blank Excel template pre-filled with all known precincts to manually track districts.")
            if not status['mprec']:
                st.error("Upload the Core Crosswalk in Tab 1 first!")
            else:
                if st.button("📄 Generate District Excel Template"):
                    res = generate_template()
                    if res["status"] == "success":
                        st.success("Generated! Download below.")
                        with open(res["dist_path"], "rb") as f:
                            st.download_button("Download Blank Template", data=f, file_name="district_assignment_template.csv", mime="text/csv")


# --- TAB 4: RUN & RESULTS ---
with tab4:
    st.markdown("### Generate Scoring Strategy")
    
    can_auto_city = auto_gen and status['city_shapefiles_ready'] and not status['city']
    can_auto_dist = auto_gen and status['dist_shapefiles_ready'] and not status['dist']
    
    if can_auto_city or can_auto_dist:
        st.info("💡 Auto-Gen Toggle is ON: System detected shapefiles and will automatically forge your missing mappings during execution!")
        
    can_run = (status['voter'] and status['mprec'] and 
               (status['city'] or can_auto_city) and 
               (status['dist'] or can_auto_dist))
    
    if not can_run:
        st.error("Cannot proceed. Missing dependencies. Review the Pipeline Status Panel above.")
    else:
        if st.button("🚀 Execute Precinct Scoring Pipeline", type="primary", use_container_width=True):
            with st.spinner("Processing massive datasets and validating integrity..."):
                
                # Check Auto-gen condition in-flight
                if can_auto_city:
                    st.toast("Auto-generating City boundaries...")
                    generate_city_assignment_from_shapes("data/srprec_shapes.zip", "data/city_shapes.zip", "data")
                if can_auto_dist:
                    st.toast("Auto-generating District boundaries...")
                    generate_district_assignment_from_shapes("data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data")
                
                # Run main logic
                result = run_pipeline(weights=weights)
                
            if result.get("status") == "validation_error":
                st.error("❌ Pipeline blocked by data validation warnings:")
                for w in result["warnings"]: st.warning(f"⚠ {w}")
                
            elif result.get("status") == "success":
                # Ensure the mathematics actually found data.
                if result.get("top_precincts", pd.DataFrame()).empty:
                    st.warning("⚠️ Analysis Completed, but NO PRECINCTS were found matching your district bounds. Check your assignment inputs.")
                else:
                    st.snow()
                    st.success("✅ Analysis & Diagnostic Generation Complete!")
                
                # ... same metric output code as before
                metrics = result["qa_metrics"]
                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(f'<div class="metric-box"><div class="metric-title">Voters</div><div class="metric-value">{metrics.get("total_voter_rows", 0):,}</div></div>', unsafe_allow_html=True)
                m2.markdown(f'<div class="metric-box"><div class="metric-title">Total SRPRECs</div><div class="metric-value">{metrics.get("total_unique_srprecs", 0):,}</div></div>', unsafe_allow_html=True)
                
                unm = metrics.get('unmatched_mprecs_count', 0)
                m3.markdown(f'<div class="metric-box"><div class="metric-title">Broken MPRECs</div><div class="metric-value" style="color: {"red" if unm>0 else "green"};">{unm:,}</div></div>', unsafe_allow_html=True)
                
                und = metrics.get('unmatched_srprecs_district_count', 0)
                m4.markdown(f'<div class="metric-box"><div class="metric-title">Unmapped Districts</div><div class="metric-value" style="color: {"red" if und>0 else "green"};">{und:,}</div></div>', unsafe_allow_html=True)
                
                # Downloads
                st.markdown("### Export Files")
                dl1, dl2 = st.columns(2)
                
                wb_path = os.path.join("outputs", "precinct_targeting_workbook.xlsx")
                if os.path.exists(wb_path):
                    with open(wb_path, "rb") as f:
                        dl1.download_button("📥 Master Excel Workbook", data=f, file_name="precinct_targeting_workbook.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
                        
                exp_path = os.path.join("outputs", "debug_explainer.txt")
                if os.path.exists(exp_path):
                    with open(exp_path, "r", encoding="utf-8") as f:
                        dl2.download_button("📄 Math Explainer (Debug Log)", data=f.read(), file_name="debug_explainer.txt", mime="text/plain", use_container_width=True, type="secondary")

                st.info("🔍 Fully transparent diagnostic files were also written to your local `outputs/run_TIMESTAMP` folder for manual auditing.")

            else:
                st.error("❌ Pipeline crashed during execution.")
                with st.expander("Show Trace"):
                    st.code(result.get("error", "Unknown error"))
