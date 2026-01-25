
import json
import urllib.request
import os
import random

# Configuration
SCRIPT_PATH = r"d:\AI\An\AutodeskDynamo_MCP\DynamoScripts\random_line.json"
URL = "http://127.0.0.1:5050/mcp/"

def run():
    print(f"Reading script template from: {SCRIPT_PATH}")
    if not os.path.exists(SCRIPT_PATH):
        print("Error: Script file not found.")
        return

    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Extract content if caught in a wrapper
        content = data.get("content", data)
        
        # Generate Random Coordinates
        coords = {
            "x1": random.randint(0, 1000),
            "y1": random.randint(0, 1000),
            "z1": random.randint(0, 500),
            "x2": random.randint(0, 1000),
            "y2": random.randint(0, 1000),
            "z2": random.randint(0, 500)
        }
        
        print(f"Generated Random Coordinates: {coords}")

        # Inject coordinates into the Number node's value
        if "nodes" in content:
            for node in content["nodes"]:
                if node.get("name") == "Number" and isinstance(node.get("value"), str):
                    original_value = node["value"]
                    # Simple string formatting
                    try:
                        new_value = original_value.format(**coords)
                        node["value"] = new_value
                        
                        # Generate a unique ID to allow multiple lines
                        import uuid
                        new_id = str(uuid.uuid4())
                        node["id"] = new_id
                        
                        print(f"Injected code into new node '{new_id}':\n{new_value}")
                    except KeyError as e:
                        print(f"Warning: Could not format string. Missing key: {e}")
        
        # Prepare payload
        json_payload = json.dumps(content)
        
        print("Sending payload to Dynamo...")
        req = urllib.request.Request(
            URL, 
            data=json_payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = response.read().decode('utf-8')
            print(f"✅ Success! Response: {result}")
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    run()
