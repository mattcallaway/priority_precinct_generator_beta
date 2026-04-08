import streamlit as st
import pandas as pd
import os
import shutil
import base64
from main import run_pipeline, generate_template

# Make sure geo_processor exists in the same folder and imports correctly
try:
    from geo_processor import generate_district_assignment_from_shapes
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
</style>
"""
st.markdown(css, unsafe_allow_html=True)
os.makedirs("data", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# Helper function to save uploaded files
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
        "shp_srprec": os.path.exists("data/srprec_shapes.zip"),
        "shp_assem": os.path.exists("data/assembly_shapes.zip"),
        "shp_sup": os.path.exists("data/supervisorial_shapes.zip")
    }
    status["shapefiles_ready"] = status["shp_srprec"] and status["shp_assem"] and status["shp_sup"]
    status["ready_to_score"] = status["voter"] and status["mprec"] and status["city"] and status["dist"]
    return status

st.title("🗺️ Priority Precinct Generator (Beta)")
st.caption("Smart Pipeline: Upload what you have — we'll fill in the gaps.")

# --- SIDEBAR: Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    auto_gen = st.toggle("Auto-generate missing datasets", value=True, help="If district data is missing but shapefiles exist, automatically generate the missing mappings without asking.")
    st.markdown("---")
    
    st.subheader("Priority Formula Weights")
    weight_turnout = st.slider("Turnout Gap", 0.0, 1.0, 0.45)
    weight_comp = st.slider("Competitive Index", 0.0, 1.0, 0.35)
    weight_density = st.slider("Voter Density", 0.0, 1.0, 0.20)
    
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
stat_cols[2].markdown(f"**City Map:** {'✅ Loaded' if status['city'] else '❌ Missing'}")

if status['dist']:
    stat_cols[3].markdown("**District Map:** ✅ Loaded")
elif status['shapefiles_ready']:
    stat_cols[3].markdown("**District Map:** 🟡 Ready to Generate")
else:
    stat_cols[3].markdown("**District Map:** ❌ Missing")

if not status['ready_to_score']:
    st.warning("Action Needed: Please provide the missing files below to unlock the Scoring Pipeline.")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📁 1. Core Data Upload", "🧩 2. District Mapping Manager", "🚀 3. Run & Results"])

# --- TAB 1: CORE DATA ---
with tab1:
    st.markdown("### Upload Core Files")
    st.info("💡 **Tip:** Don't worry if you don't have everything right now. Just upload the files you DO have.")
    
    c1, c2, c3 = st.columns(3)
    voter_up = c1.file_uploader("1. Voter File (`.csv`)", type=['csv'])
    if voter_up: save_uploaded(voter_up, "voter_file.csv")
    
    mprec_up = c2.file_uploader("2. MPREC Crosswalk (`.csv`)", type=['csv'])
    if mprec_up: save_uploaded(mprec_up, "mprec_srprec.csv")
    
    city_up = c3.file_uploader("3. City Mapping (`.csv`)", type=['csv'])
    if city_up: save_uploaded(city_up, "srprec_city.csv")

    if st.button("Refresh Status", key="ref1"):
        st.rerun()

# --- TAB 2: DISTRICT MAPPING MANAGER ---
with tab2:
    st.markdown("### District Assignment Manager")
    
    if status['dist']:
        st.success("✅ `district_assignment.csv` is already loaded into the system. You are good to go!")
        if st.button("🗑️ Remove file to start over"):
            os.remove("data/district_assignment.csv")
            st.rerun()
            
    else:
        st.warning("We are missing district assignment data. How would you like to proceed?")
        
        opt1, opt2, opt3 = st.tabs(["Option 1: Upload Existing CSV", "Option 2: Generate via Shapefiles", "Option 3: Manual Entry Template"])
        
        with opt1:
            st.write("If you already have a `district_assignment.csv` with columns `SRPREC`, `assembly_district`, `supervisorial_district`, drop it here:")
            d_up = st.file_uploader("Upload CSV", type=['csv'], key="dist_up")
            if d_up:
                save_uploaded(d_up, "district_assignment.csv")
                st.success("Saved! Refesh the app.")
                if st.button("Refresh", key="ref2"): st.rerun()
                
        with opt2:
            st.write("Upload raw GIS shapefiles representing your boundaries. We will automatically spatial-join them to your precincts!")
            if not GEO_AVAILABLE:
                st.error("Missing Geopandas dependency. Ensure you ran `pip install -r requirements.txt`.")
            else:
                st.info("💡 **Tip:** Shapefiles consist of many files. You MUST zip them up first! Upload `.zip` archives below.")
                sc1, sc2, sc3 = st.columns(3)
                shp_srprec = sc1.file_uploader("SRPREC Shapes (.zip)", type=['zip'])
                shp_assem = sc2.file_uploader("Assembly Shapes (.zip)", type=['zip'])
                shp_sup = sc3.file_uploader("Supervisor Shapes (.zip)", type=['zip'])
                
                if shp_srprec: save_uploaded(shp_srprec, "srprec_shapes.zip")
                if shp_assem: save_uploaded(shp_assem, "assembly_shapes.zip")
                if shp_sup: save_uploaded(shp_sup, "supervisorial_shapes.zip")
                
                st.write("---")
                if st.button("🗺️ Generate Assignments from Shapes", use_container_width=True, type="primary"):
                    if not (os.path.exists("data/srprec_shapes.zip") and os.path.exists("data/assembly_shapes.zip") and os.path.exists("data/supervisorial_shapes.zip")):
                        st.error("Please upload all 3 zip archives first.")
                    else:
                        with st.spinner("Crunching spatial matrices... (This can take a minute)"):
                            res = generate_district_assignment_from_shapes(
                                "data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data"
                            )
                            if res["status"] == "success":
                                st.success(f"Success! {res['message']}")
                                if res.get('ambiguous_count', 0) > 0:
                                    st.warning(f"Note: {res['ambiguous_count']} precincts fell on borders and were flagged as ambiguous.")
                            else:
                                st.error(f"Generation Failed: {res['message']}")

        with opt3:
            st.write("If you don't have map files, we can generate a blank template. It will scan your crosswalk file and list all known SRPRECs so you can type the districts into Excel manually.")
            if not status['mprec']:
                st.error("You must upload the `mprec_srprec.csv` crosswalk in Tab 1 before we can generate a template!")
            else:
                if st.button("📄 Generate Excel Template"):
                    res = generate_template()
                    if res["status"] == "success":
                        st.success("Generated! You can download it below. Fill it out locally, save it, and upload it back into Option 1.")
                        with open(res["path"], "rb") as f:
                            st.download_button("Download Blank Template", data=f, file_name="district_assignment_template.csv", mime="text/csv")
                    else:
                        st.error(res["message"])

# --- TAB 3: RUN & RESULTS ---
with tab3:
    st.markdown("### Generate Scoring Strategy")
    
    if auto_gen and status['shapefiles_ready'] and not status['dist']:
        st.info("Auto-Gen Toggle is ON: System detected shapefiles and will magically generate your missing districts during the run!")
        
    can_run = status['ready_to_score'] or (auto_gen and status['shapefiles_ready'] and status['voter'] and status['mprec'] and status['city'])
    
    if not can_run:
        st.error("Cannot proceed. Missing dependencies. Review the Pipeline Status Panel above.")
    else:
        if st.button("🚀 Execute Precinct Scoring Pipeline", type="primary", use_container_width=True):
            with st.spinner("Processing massive voter datasets..."):
                
                # Check Auto-gen condition in-flight
                status_inflight = check_status()
                if auto_gen and not status_inflight['dist'] and status_inflight['shapefiles_ready']:
                    st.toast("Auto-generating spatial maps...")
                    generate_district_assignment_from_shapes(
                        "data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data"
                    )
                
                # Run main logic
                result = run_pipeline(weights=weights)
                
            if result.get("status") == "validation_error":
                st.error("Pipeline blocked by data validation warnings:")
                for w in result["warnings"]: st.warning(f"⚠ {w}")
                
            elif result.get("status") == "success":
                st.snow()
                st.success("✅ Analysis Complete!")
                
                # Metrics
                metrics = result["qa_metrics"]
                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(f'<div class="metric-box"><div class="metric-title">Voters</div><div class="metric-value">{metrics.get("total_voter_rows", 0):,}</div></div>', unsafe_allow_html=True)
                m2.markdown(f'<div class="metric-box"><div class="metric-title">Total SRPRECs</div><div class="metric-value">{metrics.get("total_unique_srprecs", 0):,}</div></div>', unsafe_allow_html=True)
                
                unm = metrics.get('unmatched_mprecs_count', 0)
                m3.markdown(f'<div class="metric-box"><div class="metric-title">Broken MPRECs</div><div class="metric-value" style="color: {"red" if unm>0 else "green"};">{unm:,}</div></div>', unsafe_allow_html=True)
                
                und = metrics.get('unmatched_srprecs_district_count', 0)
                m4.markdown(f'<div class="metric-box"><div class="metric-title">Unmapped Districts</div><div class="metric-value" style="color: {"red" if und>0 else "green"};">{und:,}</div></div>', unsafe_allow_html=True)
                
                if und > 0:
                    st.warning(f"⚠ {und} master precincts lack district assignments (Missing Data Error). Your final overlapping targeting sheet may be missing doors!")
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.subheader("🎯 Priority Overlap (AD 12 / SD 2)")
                df = result["top_precincts"]
                if not df.empty:
                    sdf = df[['SRPREC', 'CITY', 'Total_Voters', 'Turnout_Gap_2024', 'Competitive_Index', 'Priority_Score']].copy()
                    sdf['Priority_Score'] = sdf['Priority_Score'].apply(lambda x: f"{x:.3f}")
                    st.dataframe(sdf, use_container_width=True, hide_index=True)
                else:
                    st.warning("No priority overlapping precincts found. Ensure your district mapping specifically maps to Assembly 12 and Supervisor 2.")
                
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

            else:
                st.error("❌ Pipeline crashed during execution. See Technical Error Details.")
                with st.expander("Show Trace"):
                    st.code(result.get("error", "Unknown error"))
