
import requests
import json

try:
    print("Fetching config...")
    resp = requests.get("http://localhost:8000/api/v1/system/llm-config")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("Keys:", list(data.keys()))
        print("Agent Models Map keys:", list(data.get("agent_models_map", {}).keys()))
    else:
        print("Error:", resp.text)
except Exception as e:
    print(f"Failed: {e}")
