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
import file_manager

print("[DEBUG] app.py execution cycle triggered.")

# Sync file metadata at the start of app execution
print("[DEBUG] Triggering file metadata sync...")
file_manager.sync_metadata_with_disk()

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

def get_active_contest_file():
    for ext in ['.csv', '.tsv', '.xlsx', '.xls']:
        path = f"data/contest_data_input{ext}"
        if os.path.exists(path):
            return path
    return None

def save_uploaded(file_obj, filename):
    if file_obj is not None:
        with open(os.path.join("data", filename), "wb") as f:
            f.write(file_obj.getbuffer())

# --- REAL-TIME CHECKER & DEPENDENCY MAP ---
def check_status():
    dist_exists = os.path.exists("data/district_assignment.csv")
    is_mock = False
    if dist_exists:
        try:
            df_check = pd.read_csv("data/district_assignment.csv", nrows=5)
            first_col = df_check.columns[0]
            is_mock = df_check[first_col].astype(str).str.contains("SRPREC_").any()
        except:
            is_mock = False

    status = {
        "voter": os.path.exists("data/voter_file.csv"),
        "mprec": os.path.exists("data/mprec_srprec.csv"),
        "city": os.path.exists("data/srprec_city.csv"),
        "dist": dist_exists and not is_mock,
        "is_mock_dist_present": dist_exists and is_mock,
        "metrics": os.path.exists("data/srprec_metrics.csv"),
        "has_prior_turnout": False,
        
        "shp_srprec": os.path.exists("data/srprec_shapes.zip"),
        "shp_city": os.path.exists("data/city_shapes.zip"),
        "shp_assem": os.path.exists("data/assembly_shapes.zip"),
        "shp_sup": os.path.exists("data/supervisorial_shapes.zip")
    }
    status["dist_shapefiles_ready"] = status["shp_srprec"] and status["shp_assem"] and status["shp_sup"]
    status["city_shapefiles_ready"] = status["shp_srprec"] and status["shp_city"]
    status["ready_to_score"] = status["voter"] and status["mprec"]
    
    # Check for Prior Turnout in Voter File safely
    if status["voter"]:
        try:
            head = pd.read_csv("data/voter_file.csv", nrows=1)
            cols = [c.lower().strip() for c in head.columns]
            if 'general22' in cols or any('2022' in c for c in cols):
                status["has_prior_turnout"] = True
        except:
            pass

    return status

status = check_status()

# Cached geo option extractor for dropdowns and metadata
@st.cache_data
def get_cached_geo_options(voter_file_path, mprec_path, city_path, dist_path, derive_sonoma_sd):
    from main import find_voter_geo_columns, derive_sonoma_supervisorial, is_mock_district_file, to_clean_district_str
    
    ad_opts = ["ALL"]
    sd_opts = ["ALL"]
    city_opts = ["ALL"]
    metadata = {
        "supervisorial": {"source": "unmapped", "confidence": "unknown"},
        "assembly": {"source": "unmapped", "confidence": "unknown"},
        "senate": {"source": "unmapped", "confidence": "unknown"},
        "city": {"source": "unmapped", "confidence": "unknown"}
    }
    
    if not os.path.exists(voter_file_path):
        return ad_opts, sd_opts, city_opts, metadata
        
    try:
        voter_df = pd.read_csv(voter_file_path, low_memory=False)
    except Exception as e:
        return ad_opts, sd_opts, city_opts, metadata
        
    geo_cols = find_voter_geo_columns(voter_df)
    
    # 1. City Options
    if geo_cols['city']:
        cities = voter_df[geo_cols['city']].dropna().unique().tolist()
        city_opts += sorted([str(x) for x in cities])
        metadata['city'] = {"source": "voter_file_direct", "confidence": "high"}
    elif os.path.exists(city_path):
        try:
            city_df = pd.read_csv(city_path)
            cities = city_df['city'].dropna().unique().tolist()
            city_opts += sorted([str(x) for x in cities])
            metadata['city'] = {"source": "external_mapping", "confidence": "medium"}
        except:
            pass
            
    # 2. Assembly Options
    if geo_cols['assembly']:
        ads = voter_df[geo_cols['assembly']].dropna().unique().tolist()
        ad_opts += sorted(list(set([to_clean_district_str(x) for x in ads if to_clean_district_str(x) != 'Unmapped'])))
        metadata['assembly'] = {"source": "voter_file_direct", "confidence": "high"}
    elif os.path.exists(dist_path):
        try:
            dist_df = pd.read_csv(dist_path)
            if not is_mock_district_file(dist_df, dist_path):
                ads = dist_df['assembly_district'].dropna().unique().tolist()
                ad_opts += sorted(list(set([to_clean_district_str(x) for x in ads if to_clean_district_str(x) != 'Unmapped'])))
                metadata['assembly'] = {"source": "external_mapping", "confidence": "medium"}
        except:
            pass
            
    # 3. Supervisorial Options
    if geo_cols['supervisorial']:
        sds = voter_df[geo_cols['supervisorial']].dropna().unique().tolist()
        sd_opts += sorted(list(set([to_clean_district_str(x) for x in sds if to_clean_district_str(x) != 'Unmapped'])))
        metadata['supervisorial'] = {"source": "voter_file_direct", "confidence": "high"}
    elif derive_sonoma_sd:
        derived_sds = voter_df['PrecinctName'].dropna().apply(derive_sonoma_supervisorial).dropna().unique().tolist()
        sd_opts += sorted(list(set([to_clean_district_str(x) for x in derived_sds if to_clean_district_str(x) != 'Unmapped'])))
        metadata['supervisorial'] = {"source": "precinct_prefix_rule", "confidence": "high_sonoma_verified"}
    elif os.path.exists(dist_path):
        try:
            dist_df = pd.read_csv(dist_path)
            if not is_mock_district_file(dist_df, dist_path):
                sds = dist_df['supervisorial_district'].dropna().unique().tolist()
                sd_opts += sorted(list(set([to_clean_district_str(x) for x in sds if to_clean_district_str(x) != 'Unmapped'])))
                metadata['supervisorial'] = {"source": "external_mapping", "confidence": "medium"}
        except:
            pass
            
    return ad_opts, sd_opts, city_opts, metadata

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

    st.subheader("Sonoma County Configuration")
    # Auto-detect if it is Sonoma County context
    is_sonoma = False
    if status["voter"]:
        from main import is_sonoma_context
        try:
            city_check = pd.read_csv("data/srprec_city.csv") if os.path.exists("data/srprec_city.csv") else None
        except:
            city_check = None
        is_sonoma = is_sonoma_context("data/voter_file.csv", city_check)
        
    derive_sonoma_sd = st.checkbox(
        "Derive Sonoma Supervisorial District from PrecinctName prefix",
        value=is_sonoma,
        help="Analyzes 6- or 7-digit precinct numbers to extract supervisor districts 1-5."
    )

    st.subheader("Contest Data Enrichment")
    active_contest_file = get_active_contest_file()
    contest_prec_col = None
    match_rate_val = 0.0
    config_count = 0
    if active_contest_file:
        col_file = "outputs/contest_data_manager/contest_precinct_col.txt"
        if os.path.exists(col_file):
            with open(col_file, "r") as f:
                contest_prec_col = f.read().strip()
        import contest_manager
        config_count = len(contest_manager.load_classification_config())
        if status["voter"] and contest_prec_col:
            try:
                voter_df = pd.read_csv("data/voter_file.csv", low_memory=False)
                from main import to_clean_district_str
                voter_precincts = voter_df['PrecinctName'].dropna().apply(to_clean_district_str).astype(str).str.strip().str.upper().unique().tolist()
                res_load = contest_manager.inspect_and_load_file(active_contest_file)
                if res_load["status"] == "success":
                    match_res = contest_manager.generate_precinct_match_report(res_load["df"], contest_prec_col, voter_precincts)
                    if match_res["status"] == "success":
                        match_rate_val = match_res["match_rate"]
            except:
                pass

    if active_contest_file and contest_prec_col:
        st.success(f"✅ Contest File Active ({config_count} Contests)")
        st.markdown(f"- **Precinct Match Rate:** `{match_rate_val:.1f}%`")
        contest_influence_weight = st.slider(
            "Contest Data Influence Weight", 0.0, 0.5, 0.20,
            help="Determine the percentage contribution of the contest data to the final priority score (Max 50%)."
        )
    else:
        st.info("ℹ️ Contest data not loaded. Base voter-file scoring is active.")
        contest_influence_weight = 0.0

# --- STATUS PANEL ---
st.markdown('<div class="status-box">', unsafe_allow_html=True)
st.subheader("📊 Data Dependency Status")
stat_cols = st.columns(6)
stat_cols[0].markdown(f"**Voter File:** {'✅' if status['voter'] else '❌'}")
stat_cols[1].markdown(f"**Crosswalk:** {'✅' if status['mprec'] else '❌'}")
stat_cols[2].markdown(f"**City Map:** {'✅' if status['city'] else ('🟡' if status['city_shapefiles_ready'] else '❌')}")
stat_cols[3].markdown(f"**District Map:** {'✅' if status['dist'] else ('⚠️ Mock Ignored' if status['is_mock_dist_present'] else '❌')}")
stat_cols[4].markdown(f"**True Area:** {'✅' if status['metrics'] else ('🟡' if status['shp_srprec'] else '❌')}")
stat_cols[5].markdown(f"**Contest Data:** {'✅' if active_contest_file and contest_prec_col else '❌'}")

if status['is_mock_dist_present']:
    st.warning("⚠️ Mock district_assignment.csv detected. Ignoring for production scoring.")

if not (status['voter'] and status['mprec']):
    st.warning("Action Needed: Core data files missing. Cannot proceed.")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABS ---
tab_file, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📂 Central File Manager",
    "📁 1. Core Data Upload", 
    "🏙️ 2. City Mapping Manager", 
    "🗺️ 3. District Mapping Manager", 
    "📊 4. Contest Data Manager",
    "🚀 5. Geography & Execution"
])

# --- CENTRAL FILE MANAGER TAB ---
with tab_file:
    st.markdown("### 📂 Central File Manager")
    st.markdown("Tagging files binds them to specific system roles in the precinct prioritization model.")
    
    # 1. File Upload Section
    st.subheader("📤 Add Files")
    uploaded_files = st.file_uploader("Upload CSV, TSV, or ZIP shapefiles", accept_multiple_files=True, key="fm_uploader", label_visibility="collapsed")
    if uploaded_files:
        for uf in uploaded_files:
            dest = os.path.join("data", uf.name)
            # Write only to the base data folder (avoiding archive subdirectory)
            if not os.path.exists(dest):
                with open(dest, "wb") as f:
                    f.write(uf.getbuffer())
        file_manager.sync_metadata_with_disk()
        st.success("Files uploaded successfully!")
        st.rerun()
        
    st.markdown("---")
    
    # Reload metadata
    metadata = file_manager.load_file_metadata()
    
    # 2. Active System Roles Table
    st.subheader("🎯 Active System Roles")
    
    active_mappings = {role: "❌ Unassigned" for role in file_manager.SYSTEM_ROLES.keys()}
    for fname, info in metadata.items():
        role = info.get("tag")
        if role and role in active_mappings:
            active_mappings[role] = fname
            
    role_rows = []
    for role, assigned in active_mappings.items():
        role_rows.append({
            "System Role": role,
            "Mapped File": assigned,
            "Status": "✅ Active" if assigned != "❌ Unassigned" else "⚠️ Missing"
        })
    st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # 3. User Files (Unarchived) Section
    st.subheader("📄 Managed Files (Data Folder)")
    
    unarchived_files = {k: v for k, v in metadata.items() if not v.get("archived")}
    
    if not unarchived_files:
        st.info("No unarchived user files found. Upload some files above to get started!")
    else:
        # Render a header for alignment
        c_h1, c_h2, c_h3, c_h4, c_h5 = st.columns([3, 2, 2, 2, 2])
        c_h1.markdown("**File Name & Details**")
        c_h2.markdown("**Tag/System Role**")
        c_h3.markdown("**Active Tag**")
        c_h4.markdown("**Archive Action**")
        c_h5.markdown("**Delete Action**")
        
        for fname, info in unarchived_files.items():
            path = os.path.join("data", fname)
            size_kb = os.path.getsize(path) / 1024.0 if os.path.exists(path) else 0.0
            
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
            with c1:
                st.markdown(f"📁 **{fname}**")
                st.caption(f"Size: {size_kb:.1f} KB | Updated: {info.get('uploaded_at')}")
            with c2:
                available_roles = ["None (Untagged)"] + list(file_manager.SYSTEM_ROLES.keys())
                current_tag = info.get("tag")
                default_idx = available_roles.index(current_tag) if current_tag in available_roles else 0
                
                selected_role = st.selectbox(
                    f"Tag for {fname}",
                    available_roles,
                    index=default_idx,
                    key=f"tag_select_{fname}",
                    label_visibility="collapsed"
                )
                
                if selected_role == "None (Untagged)":
                    selected_role = None
                if selected_role != current_tag:
                    success, msg = file_manager.assign_tag_role(fname, selected_role)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with c3:
                if info.get("tag"):
                    st.success(f"🏷️ {info.get('tag')}")
                else:
                    st.info("No tag")
            with c4:
                if st.button("📦 Archive", key=f"arch_btn_{fname}", use_container_width=True):
                    success, msg = file_manager.archive_file(fname)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with c5:
                if st.button("🗑️ Delete", key=f"del_btn_{fname}", use_container_width=True):
                    success, msg = file_manager.delete_file(fname)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        
    st.markdown("---")
    
    # 4. Archived Files Section
    st.subheader("📦 Archived Files")
    
    archived_files = {k: v for k, v in metadata.items() if v.get("archived")}
    
    if not archived_files:
        st.info("No files currently archived.")
    else:
        c_ah1, c_ah2, c_ah3 = st.columns([6, 3, 3])
        c_ah1.markdown("**File Name & Details**")
        c_ah2.markdown("**Restore Action**")
        c_ah3.markdown("**Delete Action**")
        
        for fname, info in archived_files.items():
            path = os.path.join("data", "archive", fname)
            size_kb = os.path.getsize(path) / 1024.0 if os.path.exists(path) else 0.0
            
            c1, c2, c3 = st.columns([6, 3, 3])
            with c1:
                st.markdown(f"📦 *{fname}*")
                st.caption(f"Size: {size_kb:.1f} KB | Archived: {info.get('uploaded_at')}")
            with c2:
                if st.button("📤 Restore / Unarchive", key=f"unarch_btn_{fname}", use_container_width=True):
                    success, msg = file_manager.unarchive_file(fname)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with c3:
                if st.button("🗑️ Permanent Delete", key=f"del_arch_btn_{fname}", use_container_width=True):
                    success, msg = file_manager.delete_file(fname)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

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
    elif status['is_mock_dist_present']:
        st.warning("⚠️ Mock `district_assignment.csv` is loaded. It will be ignored for production scoring.")
        if st.button("🗑️ Remove Mock District Mapping"): os.remove("data/district_assignment.csv"); st.rerun()
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

# --- TAB 4: CONTEST DATA MANAGER ---
with tab4:
    st.markdown("### 📊 Contest Data Manager")
    st.info("Add optional contest/results files to enrich the precinct prioritization model.")
    
    # 1. File Upload Subtab
    active_contest_file = get_active_contest_file()
    
    c_up = st.file_uploader("Upload Contest/Results File (.csv, .tsv, .xlsx, .xls)", type=['csv', 'tsv', 'xlsx', 'xls'])
    if c_up:
        # Delete existing contest inputs
        for ext in ['.csv', '.tsv', '.xlsx', '.xls']:
            p = f"data/contest_data_input{ext}"
            if os.path.exists(p):
                os.remove(p)
                
        # Save new upload
        ext = os.path.splitext(c_up.name)[1].lower()
        new_path = f"data/contest_data_input{ext}"
        with open(new_path, "wb") as f:
            f.write(c_up.getbuffer())
        st.rerun()
        
    if active_contest_file:
        st.success(f"Loaded: `{os.path.basename(active_contest_file)}`")
        if st.button("🗑️ Remove Contest File"):
            if os.path.exists(active_contest_file):
                os.remove(active_contest_file)
            col_file = "outputs/contest_data_manager/contest_precinct_col.txt"
            if os.path.exists(col_file):
                os.remove(col_file)
            st.rerun()
            
        # Inspect the file
        import contest_manager
        
        # Load sheets if Excel
        sheet_names = ["Default"]
        res_load = contest_manager.inspect_and_load_file(active_contest_file)
        if res_load["status"] == "error":
            if res_load.get("error_type") == "html_disguised_xls":
                st.error(res_load["message"])
            else:
                st.error(f"Failed to inspect file: {res_load['message']}")
        else:
            sheet_names = res_load["sheet_names"]
            selected_sheet = sheet_names[0]
            if len(sheet_names) > 1:
                selected_sheet = st.selectbox("Select Sheet/Table", sheet_names)
                
            # Run inventory
            inv = contest_manager.generate_file_inventory(active_contest_file, sheet_name=selected_sheet)
            if inv["status"] == "success":
                st.markdown(f"**Rows:** {inv['row_count']} | **Columns:** {inv['col_count']}")
                st.dataframe(inv["df"].head(5))
                
                # Precinct Mapping section
                st.markdown("#### 🗺️ 1. Precinct Mapping Matcher")
                
                # Precinct Col selection
                p_cols = inv["df"].columns.tolist()
                saved_prec_col = None
                col_file = "outputs/contest_data_manager/contest_precinct_col.txt"
                if os.path.exists(col_file):
                    with open(col_file, "r") as f:
                        saved_prec_col = f.read().strip()
                        
                default_idx = 0
                if saved_prec_col in p_cols:
                    default_idx = p_cols.index(saved_prec_col)
                elif inv["precinct_cols"]:
                    default_idx = p_cols.index(inv["precinct_cols"][0])
                    
                precinct_col = st.selectbox(
                    "Which column in this contest file identifies the precinct (PrecinctName)?",
                    p_cols,
                    index=default_idx
                )
                
                if precinct_col:
                    os.makedirs("outputs/contest_data_manager", exist_ok=True)
                    with open(col_file, "w") as f:
                        f.write(precinct_col)
                        
                    # Calculate match rate
                    if status["voter"]:
                        # Load voter precincts
                        voter_df = pd.read_csv("data/voter_file.csv", low_memory=False)
                        from main import to_clean_district_str
                        voter_precincts = voter_df['PrecinctName'].dropna().apply(to_clean_district_str).astype(str).str.strip().str.upper().unique().tolist()
                        
                        match_res = contest_manager.generate_precinct_match_report(inv["df"], precinct_col, voter_precincts)
                        if match_res["status"] == "success":
                            rate = match_res["match_rate"]
                            st.markdown(f"- **Total Contest Precincts:** {match_res['total_contest_precincts']}")
                            st.markdown(f"- **Total Voter-File Precincts:** {match_res['total_voter_precincts']}")
                            st.markdown(f"- **Exact Match Count:** {match_res['exact_match_count']}")
                            st.markdown(f"- **Match Rate:** `{rate:.1f}%`")
                            
                            if rate < 80.0:
                                st.warning(f"⚠️ **Contest data match rate is low ({rate:.1f}%).** This enrichment may be incomplete or misleading.")
                            else:
                                st.success("✅ Precinct matching threshold passed.")
                                
                # Contest Classification Wizard
                st.markdown("#### 🗳️ 2. Contest Classification Wizard")
                
                # List existing configs
                config_list = contest_manager.load_classification_config()
                if config_list:
                    st.markdown("**Currently Classified Contests:**")
                    for idx, c in enumerate(config_list):
                        st.markdown(
                            f"- **{c['name']}** ({c['contest_type']} in {c['year']}) -> "
                            f"Target: `{c['influence_component']}` | Weight: `{c['weight']}` "
                        )
                    if st.button("🗑️ Clear All Classifications"):
                        contest_manager.save_classification_config([])
                        st.rerun()
                        
                st.write("---")
                st.write("**Add Contest/Result Column:**")
                with st.form("add_contest_form"):
                    c_name = st.text_input("Contest Name (e.g. 2024 Presidential)")
                    c_year = st.number_input("Year", min_value=2000, max_value=2030, value=2024)
                    c_elec = st.selectbox("Election Type", ["General", "Primary", "Special", "Local", "Other"])
                    c_type = st.selectbox(
                        "Contest Type", 
                        ["Candidate", "Initiative / ballot measure", "Turnout", "Party baseline", "Other"]
                    )
                    
                    # Target selection
                    influence_target = st.selectbox(
                        "Influence Target component",
                        ["Support Score", "Persuasion Score", "Turnout Score", "Issue Alignment Score"]
                    )
                    c_weight = st.slider("Weight", 0.0, 1.0, 0.5)
                    
                    num_cols = inv["df"].columns.tolist()
                    
                    # Column selectors depending on type
                    fav_col = st.selectbox("Favorable Votes / Yes / Dem Column", num_cols)
                    opp_col = st.selectbox("Opposition / No Column (for Candidate type)", ["None"] + num_cols)
                    tot_col = st.selectbox("Total votes column (for Initiative/Baseline type)", ["None"] + num_cols)
                    reg_col = st.selectbox("Registered Voters column (for Turnout type)", ["None"] + num_cols)
                    
                    submit = st.form_submit_button("➕ Add Contest to Scoring Model")
                    
                    if submit and c_name:
                        # Construct contest definition
                        c_def = {
                            "name": c_name,
                            "year": int(c_year),
                            "election_type": c_elec,
                            "contest_type": c_type,
                            "influence_component": influence_target,
                            "weight": float(c_weight),
                            "favorable_col": fav_col
                        }
                        if c_type == "Candidate":
                            c_def["opposition_col"] = opp_col
                        elif c_type == "Initiative / ballot measure":
                            c_def["total_col"] = tot_col
                        elif c_type == "Turnout":
                            c_def["ballots_col"] = fav_col
                            c_def["reg_col"] = reg_col
                        elif c_type == "Party baseline":
                            c_def["total_col"] = tot_col
                            
                        config_list.append(c_def)
                        contest_manager.save_classification_config(config_list)
                        st.rerun()

# --- TAB 5: RUN & RESULTS (DYNAMIC TARGETING) ---
with tab5:
    st.markdown("### Target Extraction Parameters")
    
    can_run = status['voter'] and status['mprec']
    if not can_run:
        st.error("Missing Core Dependencies (Voter File and MPREC Crosswalk are required). Pipeline Locked.")
    else:
        ad_opts, sd_opts, city_opts, geo_metadata = get_cached_geo_options(
            "data/voter_file.csv", 
            "data/mprec_srprec.csv", 
            "data/srprec_city.csv", 
            "data/district_assignment.csv",
            derive_sonoma_sd
        )
        
        st.markdown("#### 🗺️ Geography Sources Engaged:")
        m_cols = st.columns(4)
        m_cols[0].markdown(f"**Supervisorial District:**\n\nSource: `{geo_metadata['supervisorial']['source']}`\n\nConfidence: `{geo_metadata['supervisorial']['confidence']}`")
        m_cols[1].markdown(f"**Assembly District:**\n\nSource: `{geo_metadata['assembly']['source']}`\n\nConfidence: `{geo_metadata['assembly']['confidence']}`")
        m_cols[2].markdown(f"**Senate District:**\n\nSource: `{geo_metadata['senate']['source']}`\n\nConfidence: `{geo_metadata['senate']['confidence']}`")
        m_cols[3].markdown(f"**City:**\n\nSource: `{geo_metadata['city']['source']}`\n\nConfidence: `{geo_metadata['city']['confidence']}`")
        
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
                if not status['metrics'] and status['shp_srprec']: extract_precinct_metrics("data/srprec_shapes.zip", "data")
                if not status['city'] and status['city_shapefiles_ready']: generate_city_assignment_from_shapes("data/srprec_shapes.zip", "data/city_shapes.zip", "data")
                if not status['dist'] and status['dist_shapefiles_ready']: generate_district_assignment_from_shapes("data/srprec_shapes.zip", "data/assembly_shapes.zip", "data/supervisorial_shapes.zip", "data")

                result = run_pipeline(
                    weights=weights, 
                    target_params=target_params, 
                    allow_mock=False,
                    derive_sonoma_sd=derive_sonoma_sd,
                    contest_file_path=active_contest_file,
                    contest_prec_col=contest_prec_col,
                    contest_influence_weight=contest_influence_weight
                )
                
            if result.get("status") == "validation_error":
                st.error("❌ Pipeline explicitly blocked by data validation failure:")
                for w in result["warnings"]: st.warning(f"⚠ {w}")
                
            elif result.get("status") == "success":
                top_df = result.get("top_precincts", pd.DataFrame())
                if top_df.empty:
                    st.error("❌ THE PIPELINE EXECUTED, BUT 0 PRECINCTS MATCHED YOUR TARGETING SELECTION.")
                    st.info("The overlapping condition you set does not exist. No targeting output was generated.")
                else:
                    st.success("✅ Strict Data Execution Complete.")
                    
                    # Warning for low coverage rate
                    if "Contest_Confidence" in top_df.columns and not top_df.empty:
                        # Average confidence
                        avg_conf = top_df["Contest_Confidence"].mean() * 100.0
                        if active_contest_file and contest_prec_col and avg_conf < 100.0:
                            st.warning(f"⚠️ **Warning:** Contest data covers only {avg_conf:.1f}% of precincts.")

                    metrics = result["qa_metrics"]
                    m1, m2, m3 = st.columns(3)
                    m1.markdown(f'<div class="metric-box"><div class="metric-title">Voters</div><div class="metric-value">{metrics.get("total_voter_rows", 0):,}</div></div>', unsafe_allow_html=True)
                    m2.markdown(f'<div class="metric-box"><div class="metric-title">Valid SRPRECs Found</div><div class="metric-value">{len(top_df):,}</div></div>', unsafe_allow_html=True)
                    unm = metrics.get('unmatched_mprecs_count', 0)
                    m3.markdown(f'<div class="metric-box"><div class="metric-title">Logic Breaks (Dropped MPRECs)</div><div class="metric-value" style="color: {"red" if unm>0 else "green"};">{unm:,}</div></div>', unsafe_allow_html=True)
                    
                    # Display Rank Shift Details if present
                    if "Rank_Change" in top_df.columns:
                        changed = top_df[top_df["Rank_Change"] != 0]
                        if not changed.empty:
                            st.markdown("#### 🔄 Rank Shift Analysis (Base Rank vs Final Rank)")
                            st.write(f"- **Precincts with Rank Changes:** {len(changed)} out of {len(top_df)} precincts")
                            st.write(f"- **Average Rank Shift:** {changed['Rank_Change'].abs().mean():.1f} positions")
                            st.write(f"- **Maximum Rank Shift:** {changed['Rank_Change'].abs().max()} positions")
                    
                    st.markdown("### Strict Log Files")
                    dl_cols = st.columns(2)
                    wb_path = os.path.join("outputs", "precinct_targeting_workbook.xlsx")
                    if os.path.exists(wb_path):
                        with open(wb_path, "rb") as f:
                            dl_cols[0].download_button("📥 Master Math Extractor (Excel)", data=f, file_name="precinct_targeting_workbook.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    exp_path = os.path.join("outputs", "debug_explainer.txt")
                    if os.path.exists(exp_path):
                        with open(exp_path, "r", encoding="utf-8") as f:
                            dl_cols[1].download_button("📄 Exact Component Weights Applied Log", data=f.read(), file_name="debug_explainer.txt", mime="text/plain")

                    # Add contest report download buttons if active
                    if active_contest_file and contest_prec_col:
                        st.markdown("### Contest Data Manager Outputs")
                        c_dl_cols = st.columns(3)
                        
                        brk_path = os.path.join("outputs", "contest_data_manager", "contest_scoring_breakdown.csv")
                        if os.path.exists(brk_path):
                            with open(brk_path, "r", encoding="utf-8") as f:
                                c_dl_cols[0].download_button("📥 Scoring Breakdown (CSV)", data=f.read(), file_name="contest_scoring_breakdown.csv", mime="text/csv")
                                
                        sft_path = os.path.join("outputs", "contest_data_manager", "contest_rank_shift_report.csv")
                        if os.path.exists(sft_path):
                            with open(sft_path, "r", encoding="utf-8") as f:
                                c_dl_cols[1].download_button("📥 Rank Shift Report (CSV)", data=f.read(), file_name="contest_rank_shift_report.csv", mime="text/csv")
                                
                        sum_path = os.path.join("outputs", "contest_data_manager", "contest_enrichment_summary.md")
                        if os.path.exists(sum_path):
                            with open(sum_path, "r", encoding="utf-8") as f:
                                c_dl_cols[2].download_button("📄 Enrichment Summary (Markdown)", data=f.read(), file_name="contest_enrichment_summary.md", mime="text/markdown")
            else:
                st.error("❌ Critical Pipeline Crash.")
                st.code(result.get("error", "Unknown Fault"))
