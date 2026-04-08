import streamlit as st
import pandas as pd
import os
import shutil
import base64
from main import run_pipeline

# Configure the visual style of the page
st.set_page_config(
    page_title="Priority Precinct Generator",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (premium aesthetic)
css = """
<style>
.stApp {
    background-color: #f8fafc;
}
.metric-box {
    background-color: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    text-align: center;
}
.metric-title {
    font-size: 14px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.metric-value {
    font-size: 32px;
    font-weight: bold;
    color: #0f172a;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 24px;
}
.stTabs [data-baseweb="tab"] {
    height: 50px;
    white-space: pre-wrap;
    background-color: #ffffff;
    border-radius: 4px 4px 0px 0px;
    gap: 1px;
    padding-top: 10px;
    padding-bottom: 10px;
}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

# ----------------- UI HEADERS ----------------- #
st.title("🗺️ Priority Precinct Generator (Beta)")
st.caption("Automated pipeline for campaign precinct targeting analysis.")

st.markdown("""
Welcome to the graphical interface for the Precinct Generator! This tool consumes your raw voter data and crosswalk spreadsheets to output a prioritized list of doors to knock in Assembly District 12 and Supervisorial District 2.
""")

# ----------------- SIDEBAR ----------------- #
with st.sidebar:
    st.header("⚙️ Configuration")
    st.write("Adjust the importance of each metric to recalculate priority scores.")
    
    st.subheader("Priority Formula Weights")
    weight_turnout = st.slider("Turnout Gap Weight", 0.0, 1.0, 0.45, help="Prioritizes precincts with a high raw number of non-voters.")
    weight_comp = st.slider("Competitive Index Weight", 0.0, 1.0, 0.35, help="Prioritizes 'toss-up' precincts with a 50/50 split over heavily partisan ones.")
    weight_density = st.slider("Voter Density Weight", 0.0, 1.0, 0.20, help="Prioritizes spatially larger precincts to maximize voters on a single block.")
    
    st.markdown("---")
    
    # Normalize weights so they always sum to 1.0 visually
    total_weights = weight_turnout + weight_comp + weight_density
    if total_weights == 0:
        weight_turnout, weight_comp, weight_density = 0.33, 0.33, 0.33
        total_weights = 1.0
    
    weights = {
        "turnout_gap": weight_turnout / total_weights,
        "competitive_index": weight_comp / total_weights,
        "density": weight_density / total_weights
    }
    
    st.caption(f"Normalized: \nTurnout ({weights['turnout_gap']*100:.1f}%) "
               f"\nCompetitive ({weights['competitive_index']*100:.1f}%) "
               f"\nDensity ({weights['density']*100:.1f}%)")

# ----------------- MAIN LAYOUT ----------------- #
tab1, tab2 = st.tabs(["📁 1. Data Upload", "🚀 2. Results Dashboard"])

with tab1:
    st.markdown("### Prepare Your Input Files")
    st.info("Upload exactly 4 files below. Make sure they match the required columns.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("##### 1. Voter File (`voter_file.csv`)")
        st.write("Required columns: `PrecinctName`, `Party`, `General24`, `General22`")
        voter_file = st.file_uploader("Upload Voter File", type=['csv'], key="voter")
        
        st.write("##### 2. MPREC Crosswalk (`mprec_srprec.csv`)")
        st.write("Required columns: `mprec`, `srprec`")
        mprec_file = st.file_uploader("Upload MPREC to SRPREC map", type=['csv'], key="mprec")
        
    with col2:
        st.write("##### 3. SRPREC City Map (`srprec_city.csv`)")
        st.write("Required columns: `srprec`, `city`")
        city_file = st.file_uploader("Upload SRPREC to City map", type=['csv'], key="city")
        
        st.write("##### 4. District Map (`district_assignment.csv`)")
        st.write("Required columns: `srprec`, `assembly_district`, `supervisorial_district`")
        dist_file = st.file_uploader("Upload District Map", type=['csv'], key="dist")

    # Ensure Data folder exists
    os.makedirs("data", exist_ok=True)

    validate_btn = st.button("Generate Strategy Dashboard", type="primary", use_container_width=True)

with tab2:
    if validate_btn:
        if not (voter_file and mprec_file and city_file and dist_file):
            st.error("⚠️ Please upload all 4 files in the 'Data Upload' tab before running.")
        else:
            with st.spinner("Saving data and running pipeline..."):
                # Save files locally to default locations so main.py can process them
                with open("data/voter_file.csv", "wb") as f: f.write(voter_file.getbuffer())
                with open("data/mprec_srprec.csv", "wb") as f: f.write(mprec_file.getbuffer())
                with open("data/srprec_city.csv", "wb") as f: f.write(city_file.getbuffer())
                with open("data/district_assignment.csv", "wb") as f: f.write(dist_file.getbuffer())
                
                # Execute Pipeline
                result = run_pipeline(weights=weights)
                
            if result["status"] == "success":
                st.success("✅ Analysis Complete!")
                
                # Metrics Display
                metrics = result["qa_metrics"]
                m1, m2, m3, m4 = st.columns(4)
                
                m1.markdown(f'<div class="metric-box"><div class="metric-title">Total Voters Assessed</div><div class="metric-value">{metrics.get("total_voter_rows", 0):,}</div></div>', unsafe_allow_html=True)
                m2.markdown(f'<div class="metric-box"><div class="metric-title">Master Precincts</div><div class="metric-value">{metrics.get("total_unique_srprecs", 0):,}</div></div>', unsafe_allow_html=True)
                
                unmatched_mprec = metrics.get('unmatched_mprecs_count', 0)
                color = "red" if unmatched_mprec > 0 else "green"
                m3.markdown(f'<div class="metric-box"><div class="metric-title">Unmatched Sub-Precincts</div><div class="metric-value" style="color: {color};">{unmatched_mprec:,}</div></div>', unsafe_allow_html=True)
                
                unmatched_dist = metrics.get('unmatched_srprecs_district_count', 0)
                color2 = "red" if unmatched_dist > 0 else "green"
                m4.markdown(f'<div class="metric-box"><div class="metric-title">Missing District Maps</div><div class="metric-value" style="color: {color2};">{unmatched_dist:,}</div></div>', unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Priority Dataframe
                st.subheader("🎯 Priority Overlap (AD 12 / SD 2)")
                df = result["top_precincts"]
                
                # Formatting table for better readability
                display_cols = ['SRPREC', 'CITY', 'Total_Voters', 'Turnout_Gap_2024', 'Competitive_Index', 'Priority_Score']
                if not df.empty:
                    sdf = df[display_cols].copy()
                    sdf['Competitive_Index'] = sdf['Competitive_Index'].apply(lambda x: f"{x:.2f}")
                    sdf['Priority_Score'] = sdf['Priority_Score'].apply(lambda x: f"{x:.3f}")
                    st.dataframe(sdf, use_container_width=True, hide_index=True)
                else:
                    st.warning("No precincts found that overlap AD12 and SD2.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Download Buttons
                col_dl1, col_dl2 = st.columns(2)
                
                wb_path = os.path.join("outputs", "precinct_targeting_workbook.xlsx")
                if os.path.exists(wb_path):
                    with open(wb_path, "rb") as f:
                        col_dl1.download_button(
                            label="📥 Download Master Excel Workbook",
                            data=f,
                            file_name="precinct_targeting_workbook.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            type="primary"
                        )
                
                explainer_path = os.path.join("outputs", "debug_explainer.txt")
                if os.path.exists(explainer_path):
                    with open(explainer_path, "r", encoding="utf-8") as f:
                        col_dl2.download_button(
                            label="📄 Download Debug Explainer",
                            data=f.read(),
                            file_name="debug_explainer.txt",
                            mime="text/plain",
                            use_container_width=True,
                            type="secondary"
                        )
                
            else:
                st.error("❌ Pipeline crashed during execution.")
                with st.expander("Show Technical Error Details"):
                    st.code(result.get("error", "Unknown error"))
    else:
        st.info("Upload your datasets on the left tab and click 'Generate Strategy Dashboard' to see your results.")
