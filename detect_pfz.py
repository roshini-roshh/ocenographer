import json
import xarray as xr
import numpy as np

def standardize_coords(ds):
    rename_dict = {}
    for col in ds.coords:
        if col in ["latitude", "LATITUDE"]:
            rename_dict[col] = "lat"
        elif col in ["longitude", "LONGITUDE"]:
            rename_dict[col] = "lon"
    return ds.rename(rename_dict)

def export_to_geojson(hotspots, filename="pfz_points.geojson"):
    features = []
    for p in hotspots:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [p['lon'], p['lat']]
            },
            "properties": {
                "sst": round(p['sst'], 2),
                "chl": round(p['chl'], 3)
            }
        })
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(filename, "w") as f:
        json.dump(geojson_data, f, indent=2)
    print(f"[SUCCESS] Exported {len(hotspots)} hotspots to '{filename}'")

def detect_potential_fishing_zones(sst_file="daily_sst.nc", chl_file="daily_chlorophyll.nc"):
    print("Loading datasets...")
    ds_sst = standardize_coords(xr.open_dataset(sst_file))
    ds_chl = standardize_coords(xr.open_dataset(chl_file))

    sst = ds_sst["analysed_sst"].isel(time=-1)
    if float(sst.mean()) > 100:
        sst = sst - 273.15

    chl = ds_chl["CHL"].isel(time=-1)

    print("Aligning spatial coordinates...")
    sst_resampled = sst.interp(lat=chl.lat, lon=chl.lon, method="linear")

    print("Calculating thermal gradients...")
    grad_lat = np.gradient(sst_resampled.values, axis=0)
    grad_lon = np.gradient(sst_resampled.values, axis=1)
    thermal_gradient = np.sqrt(grad_lat**2 + grad_lon**2)
    
    grad_da = xr.DataArray(
        thermal_gradient,
        coords=chl.coords,
        dims=chl.dims,
        name="sst_gradient"
    )

    # RELAXED THRESHOLDS FOR REAL-WORLD SATELLITE PASSES:
    # - Chlorophyll >= 0.2 mg/m³ (Standard coastal/pelagic productivity threshold)
    # - SST Gradient >= 0.05 °C/grid
    # - Temperature: 24°C - 31°C
    chl_mask = chl >= 0.2
    grad_mask = grad_da >= 0.05
    temp_mask = (sst_resampled >= 24.0) & (sst_resampled <= 31.0)

    pfz_mask = chl_mask & grad_mask & temp_mask

    lats = chl.lat.values
    lons = chl.lon.values
    y_indices, x_indices = np.where(pfz_mask.values)

    print(f"[RESULTS] Found {len(y_indices)} PFZ hotspot pixels.")

    hotspots = []
    # Limit export to top 100 clearest points to keep map clean
    step = max(1, len(y_indices) // 100)
    for idx in range(0, len(y_indices), step):
        lat_val = float(lats[y_indices[idx]])
        lon_val = float(lons[x_indices[idx]])
        chl_val = float(chl.values[y_indices[idx], x_indices[idx]])
        sst_val = float(sst_resampled.values[y_indices[idx], x_indices[idx]])
        
        # Skip NaNs
        if not np.isnan(chl_val) and not np.isnan(sst_val):
            hotspots.append({'lat': lat_val, 'lon': lon_val, 'sst': sst_val, 'chl': chl_val})

    # Auto-export GeoJSON for Leaflet UI
    export_to_geojson(hotspots)
    return hotspots

if __name__ == "__main__":
    detect_potential_fishing_zones()