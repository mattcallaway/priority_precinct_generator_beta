import geopandas as gpd
import pandas as pd
import logging
import os
import warnings

# Suppress annoying CRS / spatial index warnings for cleaner user output
warnings.filterwarnings("ignore")

def generate_district_assignment_from_shapes(srprec_zip, assembly_zip, sup_zip, output_dir):
    """
    Intake 3 zipped shapefiles and spatial-join the precincts to the two overlapping districts.
    Saves outputs as CSV files locally and returns status dictionaries for the UI.
    """
    logging.info("Starting Auto-generation of District Assignments from Shapefile Zips...")
    
    try:
        # 1. Load the shapefiles (geopandas can read directly from the zip path via shapefile driver)
        logging.info("Loading SRPREC shapefile.")
        srprec_gdf = gpd.read_file(f"zip://{srprec_zip}")
        
        logging.info("Loading Assembly district shapefile.")
        assem_gdf = gpd.read_file(f"zip://{assembly_zip}")
        
        logging.info("Loading Supervisorial district shapefile.")
        sup_gdf = gpd.read_file(f"zip://{sup_zip}")
        
        # 2. Harmonize Coordinate Reference Systems (CRS)
        # We project to a standard flat coordinate system (Web Mercator 3857) for accurate spatial joins and centroids.
        base_crs = "EPSG:3857"
        srprec_gdf = srprec_gdf.to_crs(base_crs)
        assem_gdf = assem_gdf.to_crs(base_crs)
        sup_gdf = sup_gdf.to_crs(base_crs)
        
        # Standardize column extraction for SRPREC ID across potentially dirty variations
        srprec_id_col = None
        for col in srprec_gdf.columns:
            if col.upper() in ['SRPREC', 'PRECINCT', 'ID', 'GEOID']:
                srprec_id_col = col
                break
                
        if not srprec_id_col:
            raise KeyError("Could not find a valid SRPREC identifier column in the SRPREC shapefile. Looking for 'SRPREC', 'PRECINCT', etc.")
            
        # Standardize Assembly District ID
        assem_id_col = None
        for col in assem_gdf.columns:
            if 'DISTRICT' in col.upper() or 'AD' in col.upper() or col.upper() in ['ID', 'GEOID', 'DIST']:
                assem_id_col = col
                break
        
        # Standardize Supervisorial District ID
        sup_id_col = None
        for col in sup_gdf.columns:
            if 'DISTRICT' in col.upper() or 'SD' in col.upper() or 'SUP' in col.upper() or col.upper() in ['ID', 'GEOID', 'DIST']:
                sup_id_col = col
                break

        if not assem_id_col or not sup_id_col:
            raise KeyError("Could not guess the identifying District column in the uploaded district shapefiles.")

        # 3. Create a clean centroid-based point dataframe for the precincts
        logging.info("Computing spatial centroids for SRPREC matching.")
        # Using Representative Point (guaranteed to be within polygon) instead of pure Centroid
        points_gdf = srprec_gdf.copy()
        points_gdf["geometry"] = points_gdf.representative_point()
        
        # 4. Perform Spatial Joins
        logging.info("Intersecting with Assembly Districts...")
        join_assem = gpd.sjoin(points_gdf, assem_gdf, how="left", predicate="intersects")
        
        logging.info("Intersecting with Supervisorial Districts...")
        # Since we just added column names from assembly, we only keep base columns + Assembly ID to avoid column collision
        clean_assem_join = join_assem[[srprec_id_col, assem_id_col, 'geometry']].copy()
        
        join_final = gpd.sjoin(clean_assem_join, sup_gdf, how="left", predicate="intersects")
        
        # 5. Extract our 3 desired columns and rename to our standardized application schema
        df_out = pd.DataFrame(join_final)
        df_out = df_out[[srprec_id_col, assem_id_col, sup_id_col]].copy()
        
        df_out.rename(columns={
            srprec_id_col: 'SRPREC',
            assem_id_col: 'assembly_district',
            sup_id_col: 'supervisorial_district'
        }, inplace=True)
        
        # Add metadata tracking fields
        df_out['assignment_method'] = 'spatial_representative_point'
        df_out['qa_flag'] = 'clear'
        
        # Clean nulls
        null_count = df_out['assembly_district'].isna().sum() + df_out['supervisorial_district'].isna().sum()
        if null_count > 0:
            df_out.loc[df_out['assembly_district'].isna() | df_out['supervisorial_district'].isna(), 'qa_flag'] = 'ambiguous_or_outside_bounds'
            logging.warning(f"Spatial Matching resulted in {null_count} null intersections.")
        
        # Output clean csv
        out_csv = os.path.join(output_dir, "district_assignment.csv")
        df_out.to_csv(out_csv, index=False)
        logging.info(f"Successfully wrote generated assignment file to {out_csv}")
        
        # Output QA
        qa_out = os.path.join(output_dir, "ambiguous_assignments.csv")
        ambig_df = df_out[df_out['qa_flag'] != 'clear']
        if not ambig_df.empty:
            ambig_df.to_csv(qa_out, index=False)
            
        return {
            "status": "success", 
            "message": f"Generated assignment file successfully. Mapped {len(df_out)} precincts.",
            "ambiguous_count": len(ambig_df)
        }
        
    except Exception as e:
        logging.error(f"Geo-processing failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

def generate_city_assignment_from_shapes(srprec_zip, city_zip, output_dir):
    """
    Intake zipped shapefiles for precincts and municipal boundaries to build srprec_city.csv
    Precincts falling outside city polygons get labeled as 'Unincorporated'.
    """
    logging.info("Starting Auto-generation of City Assignments from Shapefile Zips...")
    
    try:
        logging.info("Loading SRPREC shapefile.")
        srprec_gdf = gpd.read_file(f"zip://{srprec_zip}")
        
        logging.info("Loading City boundary shapefile.")
        city_gdf = gpd.read_file(f"zip://{city_zip}")
        
        base_crs = "EPSG:3857"
        srprec_gdf = srprec_gdf.to_crs(base_crs)
        city_gdf = city_gdf.to_crs(base_crs)
        
        srprec_id_col = None
        for col in srprec_gdf.columns:
            if col.upper() in ['SRPREC', 'PRECINCT', 'ID', 'GEOID']:
                srprec_id_col = col
                break
                
        city_id_col = None
        for col in city_gdf.columns:
            if 'CITY' in col.upper() or 'NAME' in col.upper() or 'MUNI' in col.upper():
                city_id_col = col
                break

        if not srprec_id_col or not city_id_col:
            raise KeyError("Could not guess the identifying columns in the uploaded shapefiles.")

        # Center point intersection
        points_gdf = srprec_gdf.copy()
        points_gdf["geometry"] = points_gdf.representative_point()
        
        join_city = gpd.sjoin(points_gdf, city_gdf, how="left", predicate="intersects")
        
        df_out = pd.DataFrame(join_city)
        # Handle nan for unincorporated zones
        df_out[city_id_col] = df_out[city_id_col].fillna("Unincorporated")
        
        df_out = df_out[[srprec_id_col, city_id_col]].copy()
        df_out.rename(columns={
            srprec_id_col: 'srprec',
            city_id_col: 'city'
        }, inplace=True)
        
        out_csv = os.path.join(output_dir, "srprec_city.csv")
        df_out.to_csv(out_csv, index=False)
        logging.info(f"Successfully wrote generated city mapping to {out_csv}")
        
        return {
            "status": "success", 
            "message": f"Generated City mapping file. Mapped {len(df_out)} precincts."
        }
        
    except Exception as e:
        logging.error(f"Geo-processing City failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

def extract_precinct_metrics(srprec_zip, output_dir):
    """
    Extract physical area mathematically from shapefile geometries
    to power the True Density calculation. Uses Equal Area projection (EPSG:5070)
    for physical mileage accuracy.
    """
    import geopandas as gpd
    import pandas as pd
    import logging
    import os
    logging.info("Starting Auto-extraction of Precinct Metrics...")
    try:
        srprec_gdf = gpd.read_file(f"zip://{srprec_zip}")
        
        # Reproject to CONUS Albers Equal Area for accurate area calculations
        srprec_gdf = srprec_gdf.to_crs("EPSG:5070")
        
        srprec_id_col = None
        for col in srprec_gdf.columns:
            if col.upper() in ['SRPREC', 'PRECINCT', 'ID', 'GEOID']:
                srprec_id_col = col
                break
                
        if not srprec_id_col:
            raise KeyError("Could not guess mapping identifying columns in the shapefile.")
            
        # Calculate Area in Square Miles (1 sq meter = 0.000000386102 sq miles)
        srprec_gdf['Area_Sq_Miles'] = srprec_gdf.geometry.area * 3.86102e-7
        
        df_out = srprec_gdf[[srprec_id_col, 'Area_Sq_Miles']].copy()
        df_out.rename(columns={srprec_id_col: 'srprec'}, inplace=True)
        
        out_csv = os.path.join(output_dir, "srprec_metrics.csv")
        df_out.to_csv(out_csv, index=False)
        logging.info(f"Successfully extracted Area mapping to {out_csv}")
        
        return {
            "status": "success",
            "message": "True Area metrics successfully extracted."
        }
        
    except Exception as e:
        logging.error(f"Geo-processing Metrics failed: {str(e)}")
        return {"status": "error", "message": str(e)}
