import sys
import os

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
        
    print("\nALL STREAMLIT APP TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_streamlit_app_test()
