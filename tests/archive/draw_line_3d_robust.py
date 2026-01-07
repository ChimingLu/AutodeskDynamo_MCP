import json
import urllib.request

url = "http://127.0.0.1:5050/mcp/"

# 定義起點的 3D 座標 (10, 20, 30)
# 定義終點的 3D 座標 (100, 150, 200)

instructions = {
    "nodes": [
        # 起點座標輸入 (使用 Number 節點替代 Code Block)
        {"id": "x1", "name": "Number", "value": 10, "x": -200, "y": 0},
        {"id": "y1", "name": "Number", "value": 20, "x": -200, "y": 100},
        {"id": "z1", "name": "Number", "value": 30, "x": -200, "y": 200},
        {"id": "p1", "name": "Point.ByCoordinates", "x": 100, "y": 100},

        # 終點座標輸入
        {"id": "x2", "name": "Number", "value": 100, "x": -200, "y": 400},
        {"id": "y2", "name": "Number", "value": 150, "x": -200, "y": 500},
        {"id": "z2", "name": "Number", "value": 200, "x": -200, "y": 600},
        {"id": "p2", "name": "Point.ByCoordinates", "x": 100, "y": 500},

        # 直線節點
        {"id": "line", "name": "Line.ByStartPointEndPoint", "x": 400, "y": 300}
    ],
    "connectors": [
        # 連接點 1 的輸入 (Port 0=x, 1=y, 2=z)
        {"from": "x1", "fromPort": 0, "to": "p1", "toPort": 0},
        {"from": "y1", "fromPort": 0, "to": "p1", "toPort": 1},
        {"from": "z1", "fromPort": 0, "to": "p1", "toPort": 2},

        # 連接點 2 的輸入
        {"from": "x2", "fromPort": 0, "to": "p2", "toPort": 0},
        {"from": "y2", "fromPort": 0, "to": "p2", "toPort": 1},
        {"from": "z2", "fromPort": 0, "to": "p2", "toPort": 2},

        # 連接直線
        {"from": "p1", "fromPort": 0, "to": "line", "toPort": 0},
        {"from": "p2", "fromPort": 0, "to": "line", "toPort": 1}
    ]
}

try:
    print("清空畫板並執行『穩健 3D 繪圖』指令...")
    
    # 1. Clear with special action
    clear_payload = json.dumps({"action": "clear_graph"})
    urllib.request.urlopen(urllib.request.Request(url, data=clear_payload.encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST'))

    # 2. Send composite instructions
    payload = json.dumps(instructions)
    req = urllib.request.Request(
        url, data=payload.encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        print(f"回應狀態: {resp.read().decode('utf-8')}")

except Exception as e:
    print(f"錯誤: {e}")
