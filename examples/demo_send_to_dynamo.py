import json
import urllib.request
import os

URL = "ws://127.0.0.1:65296"
SCRIPT_PATH = r"d:\AI\An\AutodeskDynamo_MCP\DynamoScripts\temp\another_line.json"

def send_instruction():
    if not os.path.exists(SCRIPT_PATH):
        print(f"Error: File not found: {SCRIPT_PATH}")
        return

    with open(SCRIPT_PATH, "r") as f:
        instruction_data = json.load(f)

    payload = json.dumps(instruction_data).encode('utf-8')
    req = urllib.request.Request(
        URL, 
        data=payload, 
        headers={'Content-Type': 'application/json'}, 
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as response:
            print(f"Response: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    send_instruction()
