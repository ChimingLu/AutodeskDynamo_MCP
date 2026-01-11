
import json
import urllib.request
import os
import random
import uuid

# Configuration
SCRIPT_PATH = r"d:\AI\An\AutodeskDynamo_MCP\DynamoScripts\welcome_test.json"
URL = "http://127.0.0.1:5050/mcp/"

def run():
    print(f"Reading script template from: {SCRIPT_PATH}")
    if not os.path.exists(SCRIPT_PATH):
        print("Error: Script file not found.")
        return

    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        content = data.get("content", data)
        
        # Geometry types available
        geom_types = ["Cuboid", "Sphere", "Cone", "Cylinder"]
        selected_type = random.choice(geom_types)
        
        # Generate Random Parameters
        params = {
            "geom_type": selected_type,
            "base_x": random.randint(0, 100),
            "base_y": random.randint(0, 500),
            "base_z": random.randint(0, 100),
            "spacing": random.randint(20, 50),
            "size": random.randint(10, 30),
            # Color 1 (RGB)
            "r1": random.randint(0, 255),
            "g1": random.randint(0, 255),
            "b1": random.randint(0, 255),
            # Color 2 (RGB)
            "r2": random.randint(0, 255),
            "g2": random.randint(0, 255),
            "b2": random.randint(0, 255),
            # Color 3 (RGB)
            "r3": random.randint(0, 255),
            "g3": random.randint(0, 255),
            "b3": random.randint(0, 255)
        }
        
        print(f"Generated Params: Type={selected_type}, Pos=({params['base_x']},{params['base_y']},{params['base_z']})")

        # Inject contents
        if "nodes" in content:
            for node in content["nodes"]:
                if node.get("name") == "Number" and isinstance(node.get("value"), str):
                    original_value = node["value"]
                    try:
                        # Use simple replacement to avoid issues with {} in DesignScript code blocks
                        new_value = original_value
                        for k, v in params.items():
                            new_value = new_value.replace(f"{{{k}}}", str(v))
                        
                        node["value"] = new_value
                        
                        # 2. Update ID to ensure new geometry every time
                        node["id"] = str(uuid.uuid4())
                        
                    except Exception as e:
                        print(f"Warning: Could not inject parameters: {e}")
        
        # Send payload
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
