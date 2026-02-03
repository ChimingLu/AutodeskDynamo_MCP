import json
import os
import random
import asyncio
import websockets
import uuid

# Configuration
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "DynamoScripts", "random_line.json")
URL = "ws://127.0.0.1:65296"

async def run():
    print(f"Reading script template from: {SCRIPT_PATH}")
    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: Script file not found at {SCRIPT_PATH}")
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
                    try:
                        new_value = original_value.format(**coords)
                        node["value"] = new_value
                        
                        # Generate a unique ID to allow multiple lines
                        new_id = f"rand_line_{uuid.uuid4().hex[:8]}"
                        node["id"] = new_id
                        
                        print(f"Injected code into node '{new_id}':\n{new_value}")
                    except KeyError as e:
                        print(f"Warning: Could not format string. Missing key: {e}")
        
        # Prepare JSON-RPC payload
        json_payload = json.dumps(content)
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "execute_dynamo_instructions",
                "arguments": {
                    "instructions": json_payload
                }
            }
        }

        print(f"Connecting to {URL}...")
        async with websockets.connect(URL) as ws:
            await ws.send(json.dumps(request))
            response = await ws.recv()
            result = json.loads(response)
            if "result" in result:
                print(f"[OK] Success! Result: {result['result']}")
            else:
                print(f"[FAIL] Error: {result.get('error')}")
            
    except Exception as e:
        print(f"[FAIL] Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run())
