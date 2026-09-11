import json
import os
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 1. Paste your actual Gemini API key string here
MY_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

# 2. Define Tool
@tool
def query_pfz_hotspots(query_region: str = "all") -> str:
    """
    Reads detected Potential Fishing Zones (PFZs) from satellite analysis.
    Returns optimal GPS coordinates, Sea Surface Temperature (SST), and Chlorophyll density.
    """
    try:
        with open("pfz_points.geojson", "r") as f:
            data = json.load(f)
            
        features = data.get("features", [])
        if not features:
            return "No active PFZ hotspots found."
        
        results = []
        for feat in features[:5]:
            coords = feat["geometry"]["coordinates"]
            props = feat["properties"]
            results.append({
                "latitude": coords[1],
                "longitude": coords[0],
                "sea_surface_temp_c": props["sst"],
                "chlorophyll_mg_m3": props["chl"]
            })
            
        return json.dumps(results, indent=2)
    except FileNotFoundError:
        return "PFZ dataset unavailable. Run detect_pfz.py first."

# 3. Prompt Setup
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are OceanAI, an AI assistant for Smart India Hackathon. "
               "You help fishermen find optimal fishing spots using satellite data. "
               "Always provide exact GPS coordinates, SST, and Chlorophyll readings."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 4. Pass key directly via google_api_key parameter
# Updated LLM configuration:
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=MY_GEMINI_KEY
)

# 5. Execute Agent
tools = [query_pfz_hotspots]
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

if __name__ == "__main__":
    print("\n--- Cloud Ocean AI Agent (Gemini) Ready ---")
    question = "Where are the best fishing spots near the southern coast of India right now?"
    
    response = agent_executor.invoke({"input": question})


    if isinstance(response["output"], list):
        clean_text = response["output"][0]["text"]
    else:
        clean_text = response["output"]

    print("\n[AI ANSWER]:\n", clean_text)   