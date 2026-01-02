import json
import urllib.request

url = "http://127.0.0.1:5050/mcp/"

# 定義具有明確 XYZ 數值的 3D 直線
# 起點 (5, 10, 15)
# 終點 (50, 80, 100)
instructions = {
    "nodes": [
        {
            "id": "p1_3d",
            "name": "Point.ByCoordinates",
            "x": 0,
            "y": 0,
            "value": "Point.ByCoordinates(5, 10, 15);"
        },
        {
            "id": "p2_3d",
            "name": "Point.ByCoordinates",
            "x": 0,
            "y": 300,
            "value": "Point.ByCoordinates(50, 80, 100);"
        },
        {
            "id": "line_3d",
            "name": "Line.ByStartPointEndPoint",
            "x": 400,
            "y": 150
        }
    ],
    "connectors": [
        { "from": "p1_3d", "fromPort": 0, "to": "line_3d", "toPort": 0 },
        { "from": "p2_3d", "fromPort": 0, "to": "line_3d", "toPort": 1 }
    ]
}

try:
    print("發送 3D 直線指令 (包含不同的 XYZ 數值)...")
    payload = json.dumps(instructions)
    req = urllib.request.Request(
        url, data=payload.encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        print(f"回應狀態: {resp.read().decode('utf-8')}")

except Exception as e:
    print(f"錯誤: {e}")
