import json
import urllib.request

url = "http://127.0.0.1:5050/mcp/"

# Using simple names that the server should resolve via common_nodes.json
instructions = {
    "nodes": [
        {
            "id": "p1",
            "name": "Point.ByCoordinates",
            "x": 0,
            "y": 0,
            "value": "Point.ByCoordinates(0,0,0);" # Optional: some handlers prefer this
        },
        {
            "id": "p2",
            "name": "Point.ByCoordinates",
            "x": 0,
            "y": 200,
            "value": "Point.ByCoordinates(10,10,0);"
        },
        {
            "id": "line1",
            "name": "Line.ByStartPointEndPoint",
            "x": 300,
            "y": 100
        }
    ],
    "connectors": [
        { "from": "p1", "fromPort": 0, "to": "line1", "toPort": 0 },
        { "from": "p2", "fromPort": 0, "to": "line1", "toPort": 1 }
    ]
}

try:
    print("Clearing workspace...")
    clear_payload = json.dumps({"action": "clear_graph"})
    urllib.request.urlopen(urllib.request.Request(url, data=clear_payload.encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST'))

    print("Sending simplified line instructions...")
    payload = json.dumps(instructions)
    req = urllib.request.Request(
        url, data=payload.encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        print(f"Status: {resp.read().decode('utf-8')}")

except Exception as e:
    print(f"Error: {e}")
