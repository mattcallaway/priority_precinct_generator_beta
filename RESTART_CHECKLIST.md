# Clean Restart Checklist

To ensure absolute pipeline integrity, the system has been hard-reset. If you are starting a fresh campaign calculation or moving to a new county, observe these steps rigorously.

- [x] **Flush the Intake Queue:** The `data/` directory is clean. If running natively, ensure no residual `.zip` files from previous geographic runs are unintentionally sitting in the folder.
- [x] **Validate Geographic Constraints:** Shapefiles MUST be zipped `.zip`. The tool no longer magically assumes data exists if it does not.
- [x] **Check Real-Time Validations:** Do not launch the pipeline unless Tab 4 ("🚀 Run") explicitly confirms all states are green. Fake execution is now locked out.
- [x] **Audit the Result:** Open `outputs/post_audit_verification_run/10_pipeline_summary.txt`. If the Match Rates are not above 95%, you must fix your input files immediately. The app will no longer coddle faulty geographic overlaps.
- [x] **Read the Breakdown:** Verify your weights natively in `07_scoring_breakdown.csv`. Turnout elasticity is now proven to ignore simple population size bias.
