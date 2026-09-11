import os
import json
import math
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
PFZ_FILE = BASE_DIR / "pfz_points.geojson"


def load_pfz_features():
    if not PFZ_FILE.exists():
        return []
    with PFZ_FILE.open("r", encoding="utf-8") as file:
        return json.load(file).get("features", [])


def calculate_distance(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def nearest_pfz(boat_lat, boat_lon):
    candidates = []
    for feature in load_pfz_features():
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        properties = feature.get("properties", {})
        if len(coordinates) < 2:
            continue
        latitude, longitude = float(coordinates[1]), float(coordinates[0])
        candidates.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "distance_km": calculate_distance(boat_lat, boat_lon, latitude, longitude),
                "sst_c": properties.get("sst"),
                "chlorophyll_mg_m3": properties.get("chl"),
            }
        )
    return min(candidates, key=lambda item: item["distance_km"]) if candidates else None


def offline_answer(question, location, pfz):
    if not pfz:
        return "No PFZ dataset is currently available."
    return (
        f"Nearest PFZ for your location is at "
        f"({pfz['latitude']:.4f}, {pfz['longitude']:.4f}), "
        f"{pfz['distance_km']:.1f} km away. "
        f"SST: {pfz['sst_c']} °C; chlorophyll: {pfz['chlorophyll_mg_m3']} mg/m³.\n\n"
        "Live weather, tide, cyclone, lightning, and geofencing feeds are not configured. "
        "Do not treat this result as a safety clearance; follow official marine warnings."
    )

TRANSLATIONS = {
    "English": {
        "title": "OceanAI Fishing Assistant",
        "location": "Set your fishing location",
        "lat": "Latitude",
        "lon": "Longitude",
        "set": "Set location",
        "nearest": "Find nearest PFZ",
        "question": "Choose a question",
        "custom": "Or type your own question",
        "ask": "Ask OceanAI",
        "warning": "Set your location before asking a location-based question. Follow official marine warnings.",
        "no_location": "Set a valid latitude and longitude first.",
        "route": "Proposed route (straight-line only)",
    },
    "മലയാളം": {
        "title": "OceanAI മത്സ്യബന്ധന സഹായി",
        "location": "മത്സ്യബന്ധന സ്ഥലം സജ്ജമാക്കുക",
        "lat": "അക്ഷാംശം",
        "lon": "രേഖാംശം",
        "set": "സ്ഥലം സജ്ജമാക്കുക",
        "nearest": "അടുത്തുള്ള PFZ കണ്ടെത്തുക",
        "question": "ഒരു ചോദ്യം തിരഞ്ഞെടുക്കുക",
        "custom": "അല്ലെങ്കിൽ സ്വന്തം ചോദ്യം എഴുതുക",
        "ask": "OceanAI-യോട് ചോദിക്കുക",
        "warning": "സ്ഥലം സജ്ജമാക്കിയ ശേഷം മാത്രം ചോദ്യം ചോദിക്കുക. ഔദ്യോഗിക കടൽ മുന്നറിയിപ്പുകൾ പാലിക്കുക.",
        "no_location": "സാധുവായ അക്ഷാംശവും രേഖാംശവും ആദ്യം നൽകുക.",
        "route": "നിർദ്ദേശിച്ച യാത്രാമാർഗം (നേരിട്ടുള്ള രേഖ മാത്രം)",
    },
    "தமிழ்": {
        "title": "OceanAI மீன்பிடி உதவியாளர்",
        "location": "மீன்பிடி இருப்பிடத்தை அமைக்கவும்",
        "lat": "அட்சரேகை",
        "lon": "தீர்க்கரேகை",
        "set": "இருப்பிடத்தை அமை",
        "nearest": "அருகிலுள்ள PFZ-ஐ கண்டறி",
        "question": "ஒரு கேள்வியைத் தேர்ந்தெடுக்கவும்",
        "custom": "அல்லது உங்கள் கேள்வியை எழுதவும்",
        "ask": "OceanAI-யிடம் கேளுங்கள்",
        "warning": "கேள்வி கேட்பதற்கு முன் இருப்பிடத்தை அமைக்கவும். அதிகாரப்பூர்வ கடல் எச்சரிக்கைகளைப் பின்பற்றவும்.",
        "no_location": "முதலில் சரியான அட்சரேகை மற்றும் தீர்க்கரேகையை உள்ளிடவும்.",
        "route": "முன்மொழியப்பட்ட பாதை (நேர்கோடு மட்டும்)",
    },
    "हिन्दी": {
        "title": "OceanAI मछली पकड़ने का सहायक",
        "location": "मछली पकड़ने का स्थान सेट करें",
        "lat": "अक्षांश",
        "lon": "देशांतर",
        "set": "स्थान सेट करें",
        "nearest": "सबसे नज़दीकी PFZ खोजें",
        "question": "एक प्रश्न चुनें",
        "custom": "या अपना प्रश्न लिखें",
        "ask": "OceanAI से पूछें",
        "warning": "स्थान आधारित प्रश्न पूछने से पहले अपना स्थान सेट करें। आधिकारिक समुद्री चेतावनियों का पालन करें।",
        "no_location": "पहले मान्य अक्षांश और देशांतर दर्ज करें।",
        "route": "प्रस्तावित मार्ग (केवल सीधी रेखा)",
    },
}

QUESTIONS = [
    "Where is the nearest Potential Fishing Zone (PFZ) today?",
    "Is it safe to venture into the sea tomorrow morning?",
    "What are the tide, weather, and sea conditions near my fishing location?",
    "Are there any lightning or cyclone alerts in my area?",
    "Which regions show high chlorophyll concentration and favourable sea surface temperature?",
    "What is the safest route for a fishing vessel considering weather and sea-state conditions?",
    "Why has fish productivity declined in a particular coastal region?",
    "Which fishing zones should be avoided due to hazardous marine conditions or geofencing restrictions?",
]

st.set_page_config(page_title="OceanAI", page_icon="🌊", layout="wide")

if "language" not in st.session_state:
    st.session_state.language = "English"
if "location" not in st.session_state:
    st.session_state.location = None
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    language = st.selectbox("Language / ഭാഷ / மொழி / भाषा", list(TRANSLATIONS), key="language")
    t = TRANSLATIONS[language]
    st.header(t["location"])
    latitude = st.number_input(t["lat"], min_value=-90.0, max_value=90.0, value=10.2152, format="%.6f")
    longitude = st.number_input(t["lon"], min_value=-180.0, max_value=180.0, value=79.2281, format="%.6f")
    if st.button(t["set"], use_container_width=True):
        st.session_state.location = (latitude, longitude)
        st.success(f"{latitude:.4f}, {longitude:.4f}")
    st.info(t["warning"])

st.title(t["title"])
st.caption("Satellite-derived PFZ indications are not a guarantee of fish availability.")

features = load_pfz_features()
location = st.session_state.location
pfz = nearest_pfz(*location) if location else None

left, right = st.columns([1, 1])
with left:
    st.subheader(t["nearest"])
    if st.button(t["nearest"], use_container_width=True):
        if not location:
            st.error(t["no_location"])
        elif not pfz:
            st.error("No PFZ dataset is currently available.")
        else:
            st.session_state.show_pfz = True
    if location and pfz:
        st.metric("Distance", f"{pfz['distance_km']:.2f} km")
        st.write(f"**GPS:** {pfz['latitude']:.4f}, {pfz['longitude']:.4f}")
        st.write(f"**Direction:** {pfz['direction']} ({pfz['bearing_degrees']}°)")
        st.write(f"**SST:** {pfz['sst_c']} °C")
        st.write(f"**Chlorophyll:** {pfz['chlorophyll_mg_m3']} mg/m³")
        st.warning("Live weather, tide, cyclone, lightning, and geofencing feeds are not configured. Do not treat this as a safety clearance.")
    elif not location:
        st.info(t["no_location"])

with right:
    st.subheader("PFZ map")
    points = [
        {"lat": feature["geometry"]["coordinates"][1], "lon": feature["geometry"]["coordinates"][0], "type": "PFZ"}
        for feature in features
        if feature.get("geometry", {}).get("coordinates")
    ]
    if location:
        points.append({"lat": location[0], "lon": location[1], "type": "Your location"})
    if pfz:
        points.append({"lat": pfz["latitude"], "lon": pfz["longitude"], "type": "Nearest PFZ"})
    if points:
        map_layers = [
            pdk.Layer(
                "ScatterplotLayer",
                pd.DataFrame(points),
                get_position="[lon, lat]",
                get_radius=12000,
                get_fill_color="[0, 180, 255, 180]",
            )
        ]
        if location and pfz:
            map_layers.append(
                pdk.Layer(
                    "LineLayer",
                    pd.DataFrame([{"from": [location[1], location[0]], "to": [pfz["longitude"], pfz["latitude"]]}]),
                    get_source_position="from",
                    get_target_position="to",
                    get_color="[255, 176, 0, 220]",
                    get_width=4,
                )
            )
        st.pydeck_chart(
            pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=location[0] if location else points[0]["lat"],
                    longitude=location[1] if location else points[0]["lon"],
                    zoom=5,
                ),
                layers=map_layers,
                tooltip={"text": "{type}\n{lat}, {lon}"},
            ),
            use_container_width=True,
        )

st.subheader("OceanAI Chat")
selected_question = st.selectbox(t["question"], [""] + QUESTIONS)
custom_question = st.text_input(t["custom"])
question = custom_question.strip() or selected_question
if st.button(t["ask"], type="primary"):
    if not location:
        st.error(t["no_location"])
    elif not question:
        st.error("Choose or enter a question.")
    else:
        answer = offline_answer(question, location, pfz)
        st.session_state.messages.append(("You", question))
        st.session_state.messages.append(("AI", answer))

for author, message in st.session_state.messages:
    with st.chat_message("user" if author == "You" else "assistant"):
        st.markdown(message)
