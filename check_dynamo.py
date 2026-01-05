import json
import urllib.request
import time

URL = "http://127.0.0.1:5050/mcp/"

def check_status():
    payload = json.dumps({"action": "get_graph_status"}).encode('utf-8')
    req = urllib.request.Request(
        URL, 
        data=payload, 
        headers={'Content-Type': 'application/json'}, 
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Status: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    check_status()
