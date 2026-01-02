import urllib.request
import json

def call_tool(name, params={}):
    url = f"http://127.0.0.1:8000/tools/{name}"
    req = urllib.request.Request(
        url, 
        data=json.dumps(params).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        return f"Error: {e}"

print("Analyzing workspace status...")
print(call_tool("analyze_workspace"))
