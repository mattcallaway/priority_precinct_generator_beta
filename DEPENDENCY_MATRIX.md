# Data Dependency Matrix

The Priority Precinct Generator is built upon conditional logic paths. Features are only unlocked when their dependent geometries or historical logs are confirmed.

| Target Capability | Required Primary Input | Acceptable Auto-Build Input | Fallback State if Missing |
| :--- | :--- | :--- | :--- |
| **City Maps** | `srprec_city.csv` | `city_shapes.zip` + `srprec_shapes.zip` | Column assigned string: `"Unmapped"` |
| **District Overlaps** | `district_assignments.csv` | `assembly_shapes.zip` + `supervisorial_shapes.zip` | Outputs 0-row result if attempting to filter |
| **True Density Rank** | `srprec_metrics.csv` | `srprec_shapes.zip` exclusively | Density weighting completely locked/disabled |
| **Turnout Elasticity** | Target Field: `general22` natively inside `voter_file.csv` | *N/A (Derived by voter history only)* | Elasticity weighting completely locked/disabled |

## UI Fall-States
The `app.py` stream evaluates these 4 vectors upon checking the local `./data/` directory. If dependencies are breached:
1. The UI will explicitly display `❌` in the Status Panel.
2. Capability Sliders will lock to `0.0`.
3. Valid Sliders will mathematically reweight to allocate `100%` distribution across the surviving variables.
