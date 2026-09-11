import asyncio
import json
import math
import os
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel

app = FastAPI(title="Ocean AI Agent API - Hybrid Architecture", version="3.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_PFZ_FILE = os.path.join(BASE_DIR, "pfz_points.geojson")
REMOTE_PFZ_URL = "https://your-remote-api.com/pfz_points.geojson"
CLOUD_AI_API_KEY = os.getenv("AI_API_KEY", "")

if os.path.exists(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

class QueryRequest(BaseModel):
    prompt: str
    boat_lat: Optional[float] = None
    boat_lon: Optional[float] = None
    language: str = "en"

def validate_coordinates(lat: Optional[float], lon: Optional[float]) -> None:
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Set your location with GPS or enter latitude and longitude before asking a location-based question.")
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Invalid coordinates. Latitude must be between -90 and 90 and longitude between -180 and 180.")

SPECIES_PROFILES = {
    "tuna": {"min_temp": 25.0, "max_temp": 30.0, "min_chl": 0.2, "max_chl": 1.2, "name": "Tuna"},
    "sardine": {"min_temp": 22.0, "max_temp": 27.0, "min_chl": 1.0, "max_chl": 5.0, "name": "Sardine / Mackerel"},
    "mackerel": {"min_temp": 22.0, "max_temp": 27.0, "min_chl": 1.0, "max_chl": 5.0, "name": "Mackerel"}
}

async def auto_sync_voyage_data():
    while True:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(REMOTE_PFZ_URL)
                if res.status_code == 200:
                    with open(LOCAL_PFZ_FILE, "wb") as f:
                        f.write(res.content)
        except Exception:
            pass
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_sync_voyage_data())

def load_pfz_features():
    if not os.path.exists(LOCAL_PFZ_FILE):
        return []
    try:
        with open(LOCAL_PFZ_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("features", [])
    except Exception:
        return []

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def bearing_direction(bearing: float) -> str:
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[round(bearing / 45) % 8]

def nearest_pfz(boat_lat: float, boat_lon: float):
    candidates = []
    for feature in load_pfz_features():
        coords = feature.get("geometry", {}).get("coordinates", [])
        props = feature.get("properties", {})
        if len(coords) < 2:
            continue
        lat, lon = float(coords[1]), float(coords[0])
        distance = calculate_distance(boat_lat, boat_lon, lat, lon)
        bearing = calculate_bearing(boat_lat, boat_lon, lat, lon)
        candidates.append({
            "latitude": lat,
            "longitude": lon,
            "distance_km": round(distance, 2),
            "bearing_degrees": round(bearing, 1),
            "direction": bearing_direction(bearing),
            "sst_c": props.get("sst"),
            "chlorophyll_mg_m3": props.get("chl"),
            "safety_status": "Unknown - live marine hazard data is not configured",
        })
    return min(candidates, key=lambda item: item["distance_km"]) if candidates else None

def detect_target_species(prompt: str):
    prompt_lower = prompt.lower()
    for species_key, profile in SPECIES_PROFILES.items():
        if species_key in prompt_lower or profile["name"].lower() in prompt_lower:
            return profile
    return None

async def query_cloud_ai(prompt: str, boat_lat: float, boat_lon: float, language: str = "en") -> Optional[str]:
    if not CLOUD_AI_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": f"You are an expert maritime oceanography AI. Vessel location: {boat_lat}°N, {boat_lon}°E. Reply in the user's selected language ({language}: en=English, ml=Malayalam, ta=Tamil, hi=Hindi). Handle queries on tides, weather, cyclone alerts, safety routes, and productivity. Never invent missing marine safety data."},
                    {"role": "user", "content": prompt}
                ]
            }
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {CLOUD_AI_API_KEY}"},
                json=payload
            )
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None

def process_query_offline(prompt: str, boat_lat: Optional[float] = None, boat_lon: Optional[float] = None, language: str = "en") -> str:
    features = load_pfz_features()
    if not features:
        return "Offline Voyage Engine: No satellite datasets loaded in local voyage pack."

    species = detect_target_species(prompt)
    prompt_lower = prompt.lower()

    is_malayalam = language == "ml" or bool(re.search(r'[\u0D00-\u0D7F]', prompt)) or any(w in prompt_lower for w in ["മീൻ", "സ്ഥലം", "കടൽ", "കാലാവസ്ഥ"])
    is_tamil = language == "ta" or bool(re.search(r'[\u0B80-\u0BFF]', prompt)) or any(w in prompt_lower for w in ["மீன்", "எங்கே", "கடல்", "வானிலை"])
    is_hindi = language == "hi" or bool(re.search(r'[\u0900-\u097F]', prompt)) or any(w in prompt_lower for w in ["मछली", "कहाँ", "मौसम", "चक्रवात"])

    matched_points = []
    for feat in features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [0, 0])
        pt_lat, pt_lon = coords[1], coords[0]
        sst, chl = props.get("sst", 0), props.get("chl", 0)
        dist_km = calculate_distance(boat_lat, boat_lon, pt_lat, pt_lon) if (boat_lat is not None and boat_lon is not None) else None

        if species:
            if species["min_temp"] <= sst <= species["max_temp"] and species["min_chl"] <= chl <= species["max_chl"]:
                matched_points.append({"lat": pt_lat, "lon": pt_lon, "sst": sst, "chl": chl, "dist": dist_km})
        else:
            matched_points.append({"lat": pt_lat, "lon": pt_lon, "sst": sst, "chl": chl, "dist": dist_km})

    if boat_lat is not None and boat_lon is not None:
        matched_points.sort(key=lambda x: x["dist"])
    else:
        matched_points.sort(key=lambda x: x["chl"], reverse=True)

    top_points = matched_points[:3]
    if not top_points:
        return "Offline Voyage Engine: No matching zones found within current local voyage parameters."

    species_label = species['name'] if species else "Fishing Zone"

    if is_malayalam:
        lines = [f"**[ഓഫ്‌ലൈൻ വോയേജ് പാക്ക്] ഏറ്റവും അടുത്തുള്ള {species_label} വിവരങ്ങൾ:**\n"]
        for idx, pt in enumerate(top_points, 1):
            d_str = f" | ദൂരം: **{pt['dist']:.1f} km**" if pt['dist'] is not None else ""
            lines.append(f"{idx}. GPS `({pt['lat']:.4f}, {pt['lon']:.4f})`{d_str} | SST: **{pt['sst']}°C** | Chlorophyll: **{pt['chl']} mg/m³**")
        return "\n".join(lines)
    elif is_tamil:
        lines = [f"**[ஆஃப்லைன் பயணம்] அருகில் உள்ள {species_label} மண்டலங்கள்:**\n"]
        for idx, pt in enumerate(top_points, 1):
            d_str = f" | தூரம்: **{pt['dist']:.1f} km**" if pt['dist'] is not None else ""
            lines.append(f"{idx}. GPS `({pt['lat']:.4f}, {pt['lon']:.4f})`{d_str} | SST: **{pt['sst']}°C** | Chlorophyll: **{pt['chl']} mg/m³**")
        return "\n".join(lines)
    elif is_hindi:
        lines = [f"**[ऑफ़लाइन यात्रा पैक] निकटतम {species_label} क्षेत्र:**\n"]
        for idx, pt in enumerate(top_points, 1):
            d_str = f" | दूरी: **{pt['dist']:.1f} km**" if pt['dist'] is not None else ""
            lines.append(f"{idx}. GPS `({pt['lat']:.4f}, {pt['lon']:.4f})`{d_str} | SST: **{pt['sst']}°C** | Chlorophyll: **{pt['chl']} mg/m³**")
        return "\n".join(lines)
    else:
        lines = [f"**[OFFLINE VOYAGE PACK] Nearest {species_label} Hotspots:**\n"]
        for idx, pt in enumerate(top_points, 1):
            d_str = f" — **{pt['dist']:.1f} km away**" if pt['dist'] is not None else ""
            lines.append(f"{idx}. GPS `({pt['lat']:.4f}, {pt['lon']:.4f})`{d_str} | SST: **{pt['sst']}°C** | Chlorophyll: **{pt['chl']} mg/m³**")
        return "\n".join(lines)

@app.get("/")
async def serve_index():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/sw.js")
async def serve_sw():
    sw_path = os.path.join(BASE_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="sw.js not found")

@app.get("/pfz_points.geojson")
async def get_geojson():
    if os.path.exists(LOCAL_PFZ_FILE):
        return FileResponse(LOCAL_PFZ_FILE)
    raise HTTPException(status_code=404, detail="pfz_points.geojson not found")

@app.post("/api/query")
async def text_query(request: QueryRequest):
    validate_coordinates(request.boat_lat, request.boat_lon)
    if CLOUD_AI_API_KEY:
        ai_response = await query_cloud_ai(request.prompt, request.boat_lat, request.boat_lon, request.language)
        if ai_response:
            return {"response": ai_response, "mode": "online-ai"}

    response_text = process_query_offline(request.prompt, request.boat_lat, request.boat_lon, request.language)
    return {"response": response_text, "mode": "offline-voyage-pack"}

@app.get("/api/nearest-pfz")
async def get_nearest_pfz(lat: float, lon: float):
    validate_coordinates(lat, lon)
    result = nearest_pfz(lat, lon)
    if result is None:
        raise HTTPException(status_code=404, detail="No PFZ data is currently available.")
    return {
        "user_location": {"latitude": lat, "longitude": lon},
        "pfz": result,
        "warning": "This is a satellite-derived fishing indication, not a guarantee of fish availability. Live weather and marine hazard feeds are not configured; follow official warnings before sailing.",
    }

LOCAL_ASSETS = {
    "leaflet.css",
    "leaflet.js",
    "leaflet.markercluster.js",
    "MarkerCluster.css",
    "MarkerCluster.Default.css",
}

@app.get("/{asset_name}")
async def serve_local_asset(asset_name: str):
    if asset_name not in LOCAL_ASSETS:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset_path = os.path.join(BASE_DIR, asset_name)
    if not os.path.isfile(asset_path):
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(asset_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)