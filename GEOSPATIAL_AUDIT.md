# Geospatial Audit Report

## Audit of Spatial Logic & Execution
**Status: BRITTLE & IDEALISTIC**

### 1. Representative Points vs Real Geometry
The system converts precinct boundaries into a single `representative_point()`, and assigns the entire precinct to whichever District Polygon that single point lands in.
- **The Danger:** Gerrymandered or wildly snaking districts commonly slice local master precincts strictly in half (e.g. northern half AD10, southern half AD12). 
- **The Result:** The Representative point mathematically forces the *entire* precinct population exclusively into one district, completely suppressing the true data from the other.
- **The Reality:** We must accept that campaigns operate on the precinct level; voters cannot be physically targeted in sub-allocations. But we MUST inform the user if their geometry is overlapping.

### 2. Missing Area Calculation
We possess the physical Polygon shapefiles in `geo_processor.py`, but we just throw away the surface area. We *need* that surface area transferred into the master pipeline so `main.py` can calculate physical Density!

### 3. CRS Harmonization
- **Finding:** The system does explicitly force `EPSG:3857`. This is excellent, as it operates in meters, allowing for legitimate area and distance calculations without lat/long spherical distortion.

## Required Spatial Repairs
1.  Add `.area` to the output of `geo_processor.py` so we can achieve real physical Density tracking.
2.  Hardcode explicit `how='left'` and `predicate='intersects'` validation checks to ensure any precinct that falls completely into the ocean triggers a hard `Unmapped` failure rather than crashing out.
