import streamlit as st
import pandas as pd
import os
import io

try:
    from geo_processor import generate_district_assignment_from_shapes, generate_city_assignment_from_shapes, extract_precinct_metrics
    GEO_AVAILABLE = True
except ImportError:
    GEO_AVAILABLE = False

from main import run_pipeline, generate_template

st.set_page_config(
    page_title="Priority Precinct Generator (Strict Mode)",
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

# --- REAL-TIME CHECKER & DEPENDENCY MAP ---
def check_status():
    status = {
        "voter": os.path.exists("data/voter_file.csv"),
        "mprec": os.path.exists("data/mprec_srprec.csv"),
        "city": os.path.exists("data/srprec_city.csv"),
        "dist": os.path.exists("data/district_assignment.csv"),
        "metrics": os.path.exists("data/srprec_metrics.csv"),
        "has_prior_turnout": False,
        
        "shp_srprec": os.path.exists("data/srprec_shapes.zip"),
        "shp_city": os.path.exists("data/city_shapes.zip"),
        "shp_assem": os.path.exists("data/assembly_shapes.zip"),
        "shp_sup": os.path.exists("data/supervisorial_shapes.zip")
    }
    status["dist_shapefiles_ready"] = status["shp_srprec"] and status["shp_assem"] and status["shp_sup"]
    status["city_shapefiles_ready"] = status["shp_srprec"] and status["shp_city"]
    status["ready_to_score"] = status["voter"] and status["mprec"] and status["city"] and status["dist"]
    
    # Check for Prior Turnout in Voter File safely
    if status["voter"]:
        try:
            head = pd.read_csv("data/voter_file.csv", nrows=1)
            cols = [c.lower().strip() for c in head.columns]
            # Looking for 2022 explicitly as a fallback rule
            if 'general22' in cols or any('2022' in c for c in cols):
                status["has_prior_turnout"] = True
        except:
            pass

    return status

status = check_status()

st.title("🗺️ Priority Precinct Generator (Strict Mode)")
st.caption("No assumptions. No fake boundaries. Only explicit inputs.")

# --- SIDEBAR: STRICT CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Score Configuration")
    st.info("The application locks capabilities that lack backing data.")
    
    can_underperf = status["has_prior_turnout"]
    can_density = status["metrics"] or status["shp_srprec"]

    st.subheader("Priority Formula Weights")
    
    weight_turnout = st.slider(
        "Turnout Elasticity", 0.0, 1.0, 0.45 if can_underperf else 0.0, 
        disabled=not can_underperf,
        help="Requires voters file with prior-cycle history (e.g. 2022 turnout)."
    )
    if not can_underperf: st.caption("❌ Unavailable: Missing Prior-Cycle Turnout")

    weight_comp = st.slider("True Competitiveness", 0.0, 1.0, 0.35)
    
    weight_density = st.slider(
        "True Density (Area)", 0.0, 1.0, 0.20 if can_density else 0.0,
        disabled=not can_density,
        help="Requires physical Map Area extracted from Precinct Shapefiles."
    )
    if not can_density: st.caption("❌ Unavailable: Missing Shapefile Area Polygons")

    # Re-normalize missing weights gracefully without throwing divide by zero
    tot = weight_turnout + weight_comp + weight_density
    if tot == 0:
        tot = 1
        weight_comp = 1.0 # fallback to absolute competitiveness
    
    weights = {
        "turnout_gap": weight_turnout/tot, 
        "competitive_index": weight_comp/tot, 
        "density": weight_density/tot
    }

# --- STATUS PANEL ---
st.markdown('<div class="status-box">', unsafe_allow_html=True)
st.subheader("📊 Data Dependency Status")
stat_cols = st.columns(5)
stat_cols[0].markdown(f"**Voter File:** {'✅' if status['voter'] else '❌'}")
stat_cols[1].markdown(f"**Crosswalk:** {'✅' if status['mprec'] else '❌'}")
stat_cols[2].markdown(f"**City Map:** {'✅' if status['city'] else ('🟡' if status['city_shapefiles_ready'] else '❌')}")
stat_cols[3].markdown(f"**District Map:** {'✅' if status['dist'] else ('🟡' if status['dist_shapefiles_ready'] else '❌')}")
stat_cols[4].markdown(f"**True Area:** {'✅' if status['metrics'] else ('🟡' if status['shp_srprec'] else '❌')}")

if not (status['voter'] and status['mprec']):
    st.warning("Action Needed: Core data files missing. Cannot proceed.")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📁 1. Core Data Upload", 
    "🏙️ 2. City Mapping Manager", 
    "🗺️ 3. District Mapping Manager", 
    "🚀 4. Geography & Execution"
])

# --- TAB 1: CORE DATA ---
with tab1:
    st.markdown("### Upload Core Voter Files")
    st.info("💡 **File Sourcing:** Grab these directly from your central Voter Database (NGP VAN / PDI). Do NOT invent mapping columns yet.")
    
    c1, c2 = st.columns(2)
    with c1:
        voter_up = st.file_uploader("1. Voter File (`voter_file.csv`)", type=['csv'])
        if voter_up: save_uploaded(voter_up, "voter_file.csv")
    with c2:
        mprec_up = st.file_uploader("2. MPREC Crosswalk (`mprec_srprec.csv`)", type=['csv'])
        if mprec_up: save_uploaded(mprec_up, "mprec_srprec.csv")
    
    if st.button("Refresh Status", key="ref1"): st.rerun()

# --- TAB 2: CITY MAPPING MANAGER ---
with tab2:
    st.markdown("### City Assignment Manager")
    if status['city']:
        st.success("✅ `srprec_city.csv` is loaded.")
        if st.button("🗑️ Remove City Mapping"): os.remove("data/srprec_city.csv"); st.rerun()
    else:
        opt1, opt2, opt3 = st.tabs(["Upload CSV", "Generate via Shapefiles", "Manual Template"])
        with opt1:
            c_up = st.file_uploader("Upload pre-made City CSV", type=['csv'], key="c1")
            if c_up: save_uploaded(c_up, "srprec_city.csv"); st.rerun()
        with opt2:
            sc1, sc2 = st.columns(2)
            shp_srprec = sc1.file_uploader("SRPREC Shapes (.zip)", type=['zip'], key="csrd")
            shp_city = sc2.file_uploader("City Shapes (.zip)", type=['zip'], key="ccyd")
            if shp_srprec: save_uploaded(shp_srprec, "srprec_shapes.zip")
            if shp_city: save_uploaded(shp_city, "city_shapes.zip")
            if st.button("🗺️ Generate City Map & Extract Area"):
                if os.path.exists("data/srprec_shapes.zip"):
                    res_m = extract_precinct_metrics("data/srprec_shapes.zip", "data")
                if os.path.exists("data/srprec_shapes.zip") and os.path.exists("data/city_shapes.zip"):
                    res = generate_city_assignment_from_shapes("data/srprec_shapes.zip", "data/city_shapes.zip", "data")
                    if res["status"] == "success": st.success("Generated!"); st.rerun()

        with opt3:
            if st.button("Generate City Template"):
                res = generate_template(); st.success("OK")

# --- TAB 3: DISTRICT MAPPING MANAGER ---
with tab3:
    st.markdown("### Legislative District Manager")
    if status['dist']:
        st.success("✅ `district_assignment.csv` is loaded.")
        if st.button("🗑️ Remove District Mapping"): os.remove("data/district_assignment.csv"); st.rerun()
    else:
        opt1, opt2, opt3 = st.tabs(["Upload CSV", "Generate via Shapefiles", "Manual Template"])
        with opt1:
            d_up = st.file_uploader("Upload District CSV", type=['csv'], key="d1")
            if d_up: save_uploaded(d_up, "district_assignment.csv"); st.rerun()
        with opt2:
            sc1, sc2, sc3 = st.columns(3)
            shp_srprec2 = sc1.file_uploader("SRPREC Shapes (.zip)", type=['zip'], key="dscrd")
            shp_assem = sc2.file_uploader("Assembly Shapes (.zip)", type=['zip'], key="dasmd")
            shp_sup = sc3.file_uploader("Supervisor Shapes (.zip)", type=['zip'], key="dsupd")
            
            if shp_srprec2: save_uploaded(shp_srprec2, "srprec_shapes.zip")
            if shp_assem: save_uploaded(shp_assem, "assembly_shapes.zip")
            if shp_sup: save_uploaded(shp_sup, "supervisorial_shapes.zip")
            
            if st.button("🗺️ Generate District Map & Extract Area", type="primary"):
                if os.path.exists("data/srprec_shapes.zip"):
                    extract_precinct_metrics("data/srprec_shapes.zip", "data")
                if os.path.exists("data/srprec_shapes.zip") and os.path.exists("data/assembly_shapes.zip") and os.path.exists("data/supervisorial_shapes.zip"):
                    res = generate_district_assignment_from_shapes("data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data")
                    if res.get("status") == "success": st.success("Generated!"); st.rerun()

        with opt3:
            if st.button("Generate District Template"): generate_template()

# --- TAB 4: RUN & RESULTS (DYNAMIC TARGETING) ---
with tab4:
    st.markdown("### Target Extraction Parameters")
    
    can_run = status['voter'] and status['mprec'] and (status['dist'] or status['dist_shapefiles_ready'])
    if not can_run:
        st.error("Missing Core Dependencies. Pipeline Locked.")
    else:
        # We must glean available districts if the file is manually loaded
        ad_opts, sd_opts, city_opts = ["ALL"], ["ALL"], ["ALL"]
        if status['dist']:
            d_read = pd.read_csv("data/district_assignment.csv")
            ad_opts += [str(x) for x in d_read.get('assembly_district', pd.Series()).dropna().unique().tolist()]
            sd_opts += [str(x) for x in d_read.get('supervisorial_district', pd.Series()).dropna().unique().tolist()]
        if status['city']:
            c_read = pd.read_csv("data/srprec_city.csv")
            city_opts += [str(x) for x in c_read.get('city', pd.Series()).dropna().unique().tolist()]
            
        st.info("Select Target Region constraints. Do not hardcode filters outside the UI.")
        c1, c2, c3 = st.columns(3)
        target_ad = c1.selectbox("Filter by Assembly District", ad_opts)
        target_sd = c2.selectbox("Filter by Supervisorial District", sd_opts)
        target_city = c3.selectbox("Filter by City", city_opts)
        
        target_params = {
            "ad": None if target_ad == "ALL" else target_ad,
            "sd": None if target_sd == "ALL" else target_sd,
            "city": None if target_city == "ALL" else target_city,
        }

        if st.button("🚀 Execute Strict Precinct Scoring", type="primary", use_container_width=True):
            with st.spinner("Executing Truth-Enforced Algorithms..."):
                # Safety auto-hook if parameters chosen but shapefiles not fired
                if not status['metrics'] and status['shp_srprec']: extract_precinct_metrics("data/srprec_shapes.zip", "data")
                if not status['city'] and status['city_shapefiles_ready']: generate_city_assignment_from_shapes("data/srprec_shapes.zip", "data/city_shapes.zip", "data")
                if not status['dist'] and status['dist_shapefiles_ready']: generate_district_assignment_from_shapes("data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data")

                result = run_pipeline(weights=weights, target_params=target_params)
                
            if result.get("status") == "validation_error":
                st.error("❌ Pipeline explicitly blocked by data validation failure:")
                for w in result["warnings"]: st.warning(f"⚠ {w}")
                
            elif result.get("status") == "success":
                top_df = result.get("top_precincts", pd.DataFrame())
                # STRICT OUTPUT FAIL-SAFE
                if top_df.empty:
                    st.error("❌ THE PIPELINE EXECUTED, BUT 0 PRECINCTS MATCHED YOUR TARGETING SELECTION.")
                    st.info("The overlapping condition you set does not exist. No targeting output was generated.")
                else:
                    st.success("✅ Strict Data Execution Complete.")
                    metrics = result["qa_metrics"]
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-box"><div class="metric-title">Voters</div><div class="metric-value">{metrics.get("total_voter_rows", 0):,}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-box"><div class="metric-title">Valid SRPRECs Found</div><div class="metric-value">{len(top_df):,}</div></div>', unsafe_allow_html=True)
                    unm = metrics.get('unmatched_mprecs_count', 0)
                    m3.markdown(f'<div class="metric-box"><div class="metric-title">Logic Breaks (Dropped MPRECs)</div><div class="metric-value" style="color: {"red" if unm>0 else "green"};">{unm:,}</div></div>', unsafe_allow_html=True)
                    
                    st.markdown("### Strict Log Files")
                    dl1, dl2 = st.columns(2)
                    wb_path = os.path.join("outputs", "precinct_targeting_workbook.xlsx")
                    if os.path.exists(wb_path):
                        with open(wb_path, "rb") as f:
                            dl1.download_button("📥 Master Math Extractor (Excel)", data=f, file_name="precinct_targeting_workbook.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    exp_path = os.path.join("outputs", "debug_explainer.txt")
                    if os.path.exists(exp_path):
                        with open(exp_path, "r", encoding="utf-8") as f:
                            dl2.download_button("📄 Exact Component Weights Applied Log", data=f.read(), file_name="debug_explainer.txt", mime="text/plain")

            else:
                st.error("❌ Critical Pipeline Crash.")
                st.code(result.get("error", "Unknown Fault"))
