from langchain.tools import tool
import json
from detect_pfz import detect_potential_fishing_zones

@tool
def query_potential_fishing_zones(min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> str:
    """
    Analyzes satellite SST gradients and Chlorophyll-a layers in the Indian Ocean.
    Returns optimal Potential Fishing Zone (PFZ) GPS coordinates, sea surface temperatures, and food density.
    """
    # Run spatial calculation engine
    hotspots = detect_potential_fishing_zones()
    
    # Filter hotspots within user-requested bounding box
    filtered = [
        p for p in hotspots 
        if min_lat <= p['lat'] <= max_lat and min_lon <= p['lon'] <= max_lon
    ]
    
    if not filtered:
        return f"No high-confidence PFZ hotspots found within coordinates [{min_lat}, {max_lat}] N, [{min_lon}, {max_lon}] E."
    
    return json.dumps(filtered[:5], indent=2)