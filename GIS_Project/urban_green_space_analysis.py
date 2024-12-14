import arcpy
import os
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

# Set up the environment
arcpy.env.overwriteOutput = True

def setup_workspace(workspace):
    """Set up the workspace and use or create a geodatabase"""
    arcpy.env.workspace = workspace
    gdb_name = "UrbanGreenSpace.gdb"
    gdb_path = os.path.join(workspace, gdb_name)
    
    if not arcpy.Exists(gdb_path):
        arcpy.CreateFileGDB_management(workspace, gdb_name)
        print(f"Created new geodatabase: {gdb_path}")
    else:
        print(f"Using existing geodatabase: {gdb_path}")
    
    return gdb_path

def find_shapefile(pattern):
    """Find a shapefile matching the given pattern"""
    for file in arcpy.ListFiles(f"*{pattern}*.shp"):
        return file
    raise FileNotFoundError(f"No shapefile matching '*{pattern}*.shp' found in the workspace")

def extract_features(input_shp, output_fc, where_clause, max_attempts=5, delay=5):
    """Extract features based on a where clause with retry mechanism"""
    for attempt in range(max_attempts):
        try:
            arcpy.Select_analysis(input_shp, output_fc, where_clause)
            print(f"Successfully extracted features to {output_fc}")
            return
        except arcpy.ExecuteError as e:
            if "ERROR 000464" in str(e) and attempt < max_attempts - 1:
                print(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise

def calculate_areas(fc):
    """Calculate the area of each feature in hectares"""
    arcpy.AddField_management(fc, "Area_Hectares", "DOUBLE")
    expression = "!shape.area@hectares!"
    arcpy.CalculateField_management(fc, "Area_Hectares", expression, "PYTHON3")

def feature_to_coords(feature_class):
    """Convert a feature class to a list of coordinates"""
    coords = []
    with arcpy.da.SearchCursor(feature_class, ["SHAPE@"]) as cursor:
        for row in cursor:
            for part in row[0]:
                for pnt in part:
                    if pnt:
                        coords.append((pnt.X, pnt.Y))
    return np.array(coords)

def create_map(green_spaces_fc, residential_fc, city_name):
    """Create a map using matplotlib"""
    fig, ax = plt.subplots(figsize=(12, 8))

    if arcpy.Exists(green_spaces_fc):
        green_spaces_coords = feature_to_coords(green_spaces_fc)
        ax.scatter(green_spaces_coords[:, 0], green_spaces_coords[:, 1], c='#2ecc71', alpha=0.7, label='Green Spaces')

    if arcpy.Exists(residential_fc):
        residential_coords = feature_to_coords(residential_fc)
        ax.scatter(residential_coords[:, 0], residential_coords[:, 1], c='#f39c12', alpha=0.4, label='Residential Areas')

    ax.set_title(f"Urban Green Space Analysis - {city_name}")
    ax.legend(loc='lower right')
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(True, linestyle='--', alpha=0.7)

    # Add North Arrow
    x, y, arrow_length = 0.95, 0.95, 0.1
    ax.annotate('N', xy=(x, y), xytext=(x, y-arrow_length),
                arrowprops=dict(facecolor='black', width=5, headwidth=15),
                ha='center', va='center', fontsize=12,
                xycoords=ax.transAxes)

    plt.tight_layout()
    return fig

def main(workspace, export_location, city_name):
    gdb_path = setup_workspace(workspace)
    
    try:
        # Extract parks and green spaces
        parks_fc = os.path.join(gdb_path, "Parks")
        extract_features(find_shapefile("landuse"), parks_fc, "fclass IN ('park', 'recreation_ground')")
        natural_fc = os.path.join(gdb_path, "NaturalAreas")
        extract_features(find_shapefile("natural"), natural_fc, "fclass IN ('forest', 'grass', 'meadow')")
        
        green_spaces_fc = os.path.join(gdb_path, "GreenSpaces")
        if arcpy.Exists(parks_fc) and arcpy.Exists(natural_fc):
            arcpy.management.Merge([parks_fc, natural_fc], green_spaces_fc)
        elif arcpy.Exists(parks_fc):
            arcpy.management.Copy(parks_fc, green_spaces_fc)
        elif arcpy.Exists(natural_fc):
            arcpy.management.Copy(natural_fc, green_spaces_fc)
        else:
            print("Warning: No green spaces found. The analysis may be incomplete.")
        
        if arcpy.Exists(green_spaces_fc):
            calculate_areas(green_spaces_fc)
        
        # Extract residential areas
        residential_fc = os.path.join(gdb_path, "Residential")
        extract_features(find_shapefile("landuse"), residential_fc, "fclass = 'residential'")
        
        # Create a map
        fig = create_map(green_spaces_fc, residential_fc, city_name)
        
        # Save as PNG and PDF
        png_path = os.path.join(export_location, f"urban_green_space_map_{city_name}.png")
        pdf_path = os.path.join(export_location, f"urban_green_space_analysis_{city_name}.pdf")
        
        plt.savefig(png_path, dpi=300, bbox_inches='tight')
        
        with PdfPages(pdf_path) as pdf:
            pdf.savefig(fig, bbox_inches='tight')
        
        plt.close()
        
        print(f"Analysis complete. Results are stored in the {gdb_path} geodatabase.")
        print(f"Map has been saved as PNG: {png_path}")
        print(f"Map has been saved as PDF: {pdf_path}")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Please ensure that all required shapefiles are in the workspace and are not being used by other applications.")

if __name__ == "__main__":
    # Set your workspace and export location here
    workspace = r"C:\GIS_Project"
    export_location = r"C:\GIS_Project\Exports"
    city_name = "Your City Name"  # Replace with the actual city name
    
    # Create export location if it doesn't exist
    os.makedirs(export_location, exist_ok=True)
    
    main(workspace, export_location, city_name)

