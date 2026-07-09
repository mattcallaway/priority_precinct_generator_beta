import sys
import os
from pathlib import Path

# Reconfigure stdout to use UTF-8 to prevent encoding errors on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add the project root directory and virtual environment site-packages to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "venv", "Lib", "site-packages"))

from streamlit.testing.v1 import AppTest

def run_streamlit_app_test():
    print("Initializing Streamlit AppTest for app.py...")
    # Point to app.py
    at = AppTest.from_file("app.py", default_timeout=120)
    
    # Run the initial render
    at.run()
    
    # Check for exceptions on first render
    if at.exception:
        print("FAIL: Exception during initial run:")
        print(at.exception)
        sys.exit(1)
        
    print("PASS: App rendered initially with no exceptions.")
    
    # Let's inspect sidebars/tabs
    title_val = at.title[0].value if at.title else 'No Title'
    print(f"Detected title: {title_val}")
    
    # Let's check sliders
    print("Found Sliders:")
    for slider in at.slider:
        print(f" - {slider.label}: current value = {slider.value}")
        
    # Trigger execution button
    # The execution button is: st.button("🚀 Execute ...")
    execute_button = None
    for btn in at.button:
        if "Execute" in btn.label:
            execute_button = btn
            break
            
    if execute_button:
        print("Found execution button. Clicking it...")
        execute_button.click().run()
        if at.exception:
            print("FAIL: Exception after clicking execute button:")
            print(at.exception)
            sys.exit(1)
        else:
            print("PASS: App executed pipeline and finished without exceptions.")
    else:
        print("WARNING: Could not find Execute button (may be disabled/hidden because of missing core files).")
        
    # Test manifest and zip helpers directly
    print("\nRunning persistent download panel regression tests...")
    import app
    
    # Simulate a successful run context
    run_ctx = {
        "run_mode": "USER_DASHBOARD_MODE",
        "active_voter_file": "data/voter_file.csv",
        "active_contest_file": "data/contest_data_input.csv",
        "active_cross_reference_files": [],
        "readiness_verdict": "PRODUCTION_READY_WITH_INHERITED_CONTEST_SIGNALS"
    }
    
    # 1. Build manifest
    manifest = app.build_output_manifest(run_ctx)
    print(f"Number of candidates in manifest: {len(manifest)}")
    if len(manifest) < 20:
        print(f"FAIL: Expected at least 20 files in manifest, got {len(manifest)}")
        sys.exit(1)
        
    # Check that required files are correctly marked
    required_labels = [
        "Production Priority Precincts CSV",
        "Top 50 Explainability Table",
        "Final Validation Summary",
        "Contest Scope Validation",
        "Final Config Reconciliation Verdict"
    ]
    manifest_labels = [item["label"] for item in manifest]
    for rl in required_labels:
        if rl not in manifest_labels:
            print(f"FAIL: Required label '{rl}' not found in manifest")
            sys.exit(1)
    print("PASS: Verified required campaign outputs exist in manifest definitions.")
    
    # 2. Test ZIP creation
    zip_path = app.create_outputs_zip(manifest, run_ctx)
    print(f"Zip created at: {zip_path}")
    if not zip_path.exists():
        print("FAIL: Zip file was not created")
        sys.exit(1)
        
    # Inspect Zip contents
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        print(f"Files included in Download All ZIP: {namelist}")
        # Must include download_manifest.json
        if "download_manifest.json" not in namelist:
            print("FAIL: download_manifest.json not found in ZIP")
            sys.exit(1)
            
        # Verify required files are included if they exist on disk
        for item in manifest:
            if item["exists"]:
                rel_p = str(Path(item["file_path"]).relative_to("outputs")).replace("\\", "/")
                if rel_p not in namelist:
                    print(f"FAIL: Expected file '{rel_p}' in ZIP namelist, but it was missing.")
                    sys.exit(1)
                    
    print("PASS: ZIP file contents verified successfully.")
    print("\nALL STREAMLIT APP TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_streamlit_app_test()

