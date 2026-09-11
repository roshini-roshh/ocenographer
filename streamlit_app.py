import os
import json
import math
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
from streamlit_geolocation import streamlit_geolocation
from zipfile import ZIP_DEFLATED, ZipFile
from io import BytesIO

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


def calculate_bearing(lat1, lon1, lat2, lon2):
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2_rad)
    y = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_direction(bearing):
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return directions[round(bearing / 45) % 8]


def nearest_pfz(boat_lat, boat_lon):
    candidates = []
    for feature in load_pfz_features():
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        properties = feature.get("properties", {})
        if len(coordinates) < 2:
            continue
        latitude, longitude = float(coordinates[1]), float(coordinates[0])
        bearing = calculate_bearing(boat_lat, boat_lon, latitude, longitude)
        candidates.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "distance_km": calculate_distance(boat_lat, boat_lon, latitude, longitude),
                "bearing_degrees": round(bearing, 1),
                "direction": bearing_direction(bearing),
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


def localized_answer(language, pfz):
    values = (
        f"{pfz['latitude']:.4f}, {pfz['longitude']:.4f}",
        f"{pfz['distance_km']:.1f}",
        str(pfz["sst_c"]),
        str(pfz["chlorophyll_mg_m3"]),
    )
    answers = {
        "മലയാളം": (
            f"നിങ്ങളുടെ സ്ഥലത്തിന് ഏറ്റവും അടുത്തുള്ള PFZ: **{values[0]}**\n\n"
            f"ദൂരം: **{values[1]} കിലോമീറ്റർ**\n\n"
            f"കടൽ ഉപരിതല താപനില: **{values[2]}°C**\n\n"
            f"ക്ലോറോഫിൽ: **{values[3]} mg/m³**\n\n"
            "തത്സമയ കാലാവസ്ഥ, വേലിയേറ്റം, ചുഴലിക്കാറ്റ്, മിന്നൽ, ജിയോഫെൻസിംഗ് വിവരങ്ങൾ ലഭ്യമല്ല. "
            "യാത്രയ്ക്ക് മുമ്പ് ഔദ്യോഗിക കടൽ മുന്നറിയിപ്പുകൾ പരിശോധിക്കുക."
        ),
        "தமிழ்": (
            f"உங்கள் இருப்பிடத்திற்கு அருகிலுள்ள PFZ: **{values[0]}**\n\n"
            f"தூரம்: **{values[1]} கி.மீ.**\n\n"
            f"கடல் மேற்பரப்பு வெப்பநிலை: **{values[2]}°C**\n\n"
            f"குளோரோபில்: **{values[3]} mg/m³**\n\n"
            "நேரடி வானிலை, அலை, சூறாவளி, மின்னல் மற்றும் கட்டுப்பாட்டு தகவல்கள் இல்லை. "
            "பயணத்திற்கு முன் அதிகாரப்பூர்வ கடல் எச்சரிக்கைகளைச் சரிபார்க்கவும்."
        ),
        "हिन्दी": (
            f"आपके स्थान के लिए सबसे नज़दीकी PFZ: **{values[0]}**\n\n"
            f"दूरी: **{values[1]} किमी**\n\n"
            f"समुद्री सतह का तापमान: **{values[2]}°C**\n\n"
            f"क्लोरोफिल: **{values[3]} mg/m³**\n\n"
            "लाइव मौसम, ज्वार, चक्रवात, बिजली और प्रतिबंधित क्षेत्र की जानकारी उपलब्ध नहीं है। "
            "यात्रा से पहले आधिकारिक समुद्री चेतावनियां जांचें।"
        ),
    }
    return answers.get(language, offline_answer("", None, pfz))

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
        "gps": "Use current GPS location",
        "voyage_pack": "Download voyage map pack",
        "map": "PFZ map",
        "chat": "OceanAI Chat",
        "caption": "Satellite-derived PFZ indications are not a guarantee of fish availability.",
        "questions": [],
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
        "gps": "നിലവിലെ GPS സ്ഥലം ഉപയോഗിക്കുക",
        "voyage_pack": "യാത്രാ മാപ്പ് പാക്ക് ഡൗൺലോഡ് ചെയ്യുക",
        "map": "PFZ മാപ്പ്",
        "chat": "OceanAI ചാറ്റ്",
        "caption": "സാറ്റലൈറ്റ് വിവരങ്ങളിൽ നിന്നുള്ള PFZ സൂചനകൾ മത്സ്യം ലഭിക്കുമെന്ന ഉറപ്പല്ല.",
        "questions": ["ഇന്നത്തെ ഏറ്റവും അടുത്തുള്ള സാധ്യതയുള്ള മത്സ്യബന്ധന മേഖല (PFZ) ഏതാണ്?", "നാളെ രാവിലെ കടലിൽ പോകുന്നത് സുരക്ഷിതമാണോ?", "എന്റെ മത്സ്യബന്ധന സ്ഥലത്തെ വേലിയേറ്റം, കാലാവസ്ഥ, കടൽസ്ഥിതി എന്താണ്?", "എന്റെ പ്രദേശത്ത് മിന്നൽ അല്ലെങ്കിൽ ചുഴലിക്കാറ്റ് മുന്നറിയിപ്പുണ്ടോ?", "ഉയർന്ന ക്ലോറോഫിൽ സാന്ദ്രതയും അനുയോജ്യമായ കടൽ ഉപരിതല താപനിലയുമുള്ള മേഖലകൾ ഏവ?", "മത്സ്യബന്ധന ബോട്ടിന് ഏറ്റവും സുരക്ഷിതമായ യാത്രാമാർഗം ഏതാണ്?", "ഈ തീരപ്രദേശത്ത് മത്സ്യ ഉൽപ്പാദനം കുറഞ്ഞത് എന്തുകൊണ്ട്?", "അപകടകരമോ നിയന്ത്രിതമോ ആയതിനാൽ ഒഴിവാക്കേണ്ട മത്സ്യബന്ധന മേഖലകൾ ഏവ?"],
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
        "gps": "தற்போதைய GPS இருப்பிடத்தைப் பயன்படுத்து",
        "voyage_pack": "பயண வரைபட தொகுப்பைப் பதிவிறக்கு",
        "map": "PFZ வரைபடம்",
        "chat": "OceanAI அரட்டை",
        "caption": "செயற்கைக்கோள் PFZ தகவல் மீன் கிடைப்பதற்கான உத்தரவாதம் அல்ல.",
        "questions": ["இன்றைய அருகிலுள்ள சாத்தியமான மீன்பிடி மண்டலம் (PFZ) எது?", "நாளை காலை கடலுக்குச் செல்வது பாதுகாப்பானதா?", "எனது மீன்பிடி இடத்திற்கு அருகிலுள்ள அலை, வானிலை மற்றும் கடல் நிலை என்ன?", "எனது பகுதியில் மின்னல் அல்லது சூறாவளி எச்சரிக்கைகள் உள்ளனவா?", "அதிக குளோரோபில் மற்றும் சாதகமான கடல் மேற்பரப்பு வெப்பநிலை உள்ள பகுதிகள் எவை?", "மீன்பிடி படகிற்கு பாதுகாப்பான பாதை எது?", "இந்தக் கடலோரப் பகுதியில் மீன் உற்பத்தி ஏன் குறைந்தது?", "ஆபத்து அல்லது கட்டுப்பாடுகள் காரணமாக தவிர்க்க வேண்டிய மீன்பிடி மண்டலங்கள் எவை?"],
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
        "gps": "वर्तमान GPS स्थान का उपयोग करें",
        "voyage_pack": "यात्रा मानचित्र पैक डाउनलोड करें",
        "map": "PFZ मानचित्र",
        "chat": "OceanAI चैट",
        "caption": "उपग्रह से प्राप्त PFZ संकेत मछली मिलने की गारंटी नहीं हैं।",
        "questions": ["आज का सबसे नज़दीकी संभावित मछली पकड़ने का क्षेत्र (PFZ) कहाँ है?", "क्या कल सुबह समुद्र में जाना सुरक्षित है?", "मेरे मछली पकड़ने के स्थान के पास ज्वार, मौसम और समुद्र की स्थिति कैसी है?", "क्या मेरे क्षेत्र में बिजली या चक्रवात की चेतावनी है?", "कौन से क्षेत्रों में अधिक क्लोरोफिल और अनुकूल समुद्री सतह का तापमान है?", "मछली पकड़ने वाली नाव के लिए सबसे सुरक्षित मार्ग कौन सा है?", "इस तटीय क्षेत्र में मछली उत्पादकता क्यों कम हुई?", "खतरनाक या प्रतिबंधित होने के कारण किन मछली पकड़ने वाले क्षेत्रों से बचना चाहिए?"],
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
TRANSLATIONS["English"]["questions"] = QUESTIONS

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
    gps_location = streamlit_geolocation()
    if gps_location and gps_location.get("latitude") is not None and gps_location.get("longitude") is not None:
        st.session_state.location = (
            float(gps_location["latitude"]),
            float(gps_location["longitude"]),
        )
        st.success(t["gps"])
    latitude = st.number_input(t["lat"], min_value=-90.0, max_value=90.0, value=10.2152, format="%.6f")
    longitude = st.number_input(t["lon"], min_value=-180.0, max_value=180.0, value=79.2281, format="%.6f")
    if st.button(t["set"], use_container_width=True):
        st.session_state.location = (latitude, longitude)
        st.success(f"{latitude:.4f}, {longitude:.4f}")
    voyage_pack = BytesIO()
    with ZipFile(voyage_pack, "w", ZIP_DEFLATED) as archive:
        archive.writestr("pfz_points.geojson", PFZ_FILE.read_text(encoding="utf-8"))
        archive.writestr(
            "README.txt",
            "OceanAI voyage pack. PFZ data is satellite-derived and does not replace official marine safety warnings.\n",
        )
    st.download_button(
        label=f"📥 {t['voyage_pack']}",
        data=voyage_pack.getvalue(),
        file_name="oceanai-voyage-pack.zip",
        mime="application/zip",
        use_container_width=True,
    )
    st.info(t["warning"])

st.title(t["title"])
st.caption(t["caption"])

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
    st.subheader(t["map"])
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

st.subheader(t["chat"])
selected_question = st.selectbox(t["question"], [""] + t["questions"])
custom_question = st.text_input(t["custom"])
question = custom_question.strip() or selected_question
if st.button(t["ask"], type="primary"):
    if not location:
        st.error(t["no_location"])
    elif not question:
        st.error("Choose or enter a question.")
    else:
        answer = localized_answer(language, pfz)
        st.session_state.messages.append(("You", question))
        st.session_state.messages.append(("AI", answer))

for author, message in st.session_state.messages:
    with st.chat_message("user" if author == "You" else "assistant"):
        st.markdown(message)
