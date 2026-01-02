import json
import urllib.request

url = "http://127.0.0.1:5050/mcp/"

instructions = {
    "nodes": [
        {
            "id": "p1",
            "name": "Autodesk.DesignScript.Geometry.Point.ByCoordinates@double,double,double",
            "x": 0,
            "y": 0,
            "properties": { "x": 0, "y": 0, "z": 0 }
        },
        {
            "id": "p2",
            "name": "Autodesk.DesignScript.Geometry.Point.ByCoordinates@double,double,double",
            "x": 0,
            "y": 200,
            "properties": { "x": 10, "y": 10, "z": 0 }
        },
        {
            "id": "line1",
            "name": "Autodesk.DesignScript.Geometry.Line.ByStartPointEndPoint",
            "x": 300,
            "y": 100
        }
    ],
    "connectors": [
        { "fromNode": "p1", "fromPort": "Point", "toNode": "line1", "toPort": "startPoint" },
        { "fromNode": "p2", "fromPort": "Point", "toNode": "line1", "toPort": "endPoint" }
    ]
}

# Clear workspace first
clear_payload = json.dumps({"action": "clear_graph"})
try:
    print("Clearing workspace...")
    req_clear = urllib.request.Request(
        url, data=clear_payload.encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req_clear) as resp:
        print(f"Clear status: {resp.read().decode('utf-8')}")

    print("Sending line instructions...")
    payload = json.dumps(instructions)
    req = urllib.request.Request(
        url, data=payload.encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        print(f"Instruction status: {resp.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
