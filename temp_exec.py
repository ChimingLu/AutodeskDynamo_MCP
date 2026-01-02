import urllib.request
import json
import os

script_path = r'd:\AI\An\AutodeskDynamo_MCP\DynamoScripts\solid_demo.json'
with open(script_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

instructions = json.dumps(data['content'])
payload = json.dumps({
    'instructions': instructions,
    'clear_before_execute': True
})

url = 'http://127.0.0.1:5050/mcp/'
req = urllib.request.Request(
    url, 
    data=payload.encode('utf-8'), 
    headers={'Content-Type': 'application/json'}, 
    method='POST'
)

with urllib.request.urlopen(req) as resp:
    print(resp.read().decode('utf-8'))
