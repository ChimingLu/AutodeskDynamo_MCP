
import asyncio
import websockets
import json
import uuid

async def main():
    """
    示範如何在 Dynamo 中建立原生節點、建立連線，
    並自動關閉中間過程節點的預覽 (Preview)，以清晰展示布林運算的最終結果。
    """
    uri = "ws://127.0.0.1:65296"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")

            # 1. 清除工作區 (確保環境乾淨)
            await websocket.send(json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "clear_workspace", "arguments": {}},
                "id": str(uuid.uuid4())
            }))
            await websocket.recv()

            # 2. 定義原生節點圖示
            # 重點：設定 "preview": false 來隱藏中間幾何體
            instructions = {
                "nodes": [
                    # 參數節點
                    {"id": "num0", "name": "Number", "value": "0", "x": 0, "y": 0},
                    {"id": "num80", "name": "Number", "value": "80", "x": 0, "y": 120},
                    {"id": "num100", "name": "Number", "value": "100", "x": 0, "y": 240},
                    
                    # 點 (隱藏預覽，避免遮擋結果)
                    {"id": "pt1", "name": "Point.ByCoordinates", "overload": "3D", "preview": False, "x": 250, "y": 0},
                    {"id": "pt2", "name": "Point.ByCoordinates", "overload": "3D", "preview": False, "x": 250, "y": 200},
                    
                    # 球體 (隱藏預覽)
                    {"id": "sph1", "name": "Sphere.ByCenterPointRadius", "preview": False, "x": 550, "y": 0},
                    {"id": "sph2", "name": "Sphere.ByCenterPointRadius", "preview": False, "x": 550, "y": 200},
                    
                    # 布林運算結果 (保持預覽開啟)
                    {"id": "bool_op", "name": "Solid.Difference", "preview": True, "x": 850, "y": 100}
                ],
                "connectors": [
                    # 注意：C# 橋接器要求使用 'fromPort' 與 'toPort' 欄位
                    {"from": "num0", "to": "pt1", "fromPort": 0, "toPort": 0},
                    {"from": "num0", "to": "pt1", "fromPort": 0, "toPort": 1},
                    {"from": "num0", "to": "pt1", "fromPort": 0, "toPort": 2},
                    {"from": "num80", "to": "pt2", "fromPort": 0, "toPort": 0},
                    {"from": "num0", "to": "pt2", "fromPort": 0, "toPort": 1},
                    {"from": "num0", "to": "pt2", "fromPort": 0, "toPort": 2},
                    {"from": "pt1", "to": "sph1", "fromPort": 0, "toPort": 0},
                    {"from": "num100", "to": "sph1", "fromPort": 0, "toPort": 1},
                    {"from": "pt2", "to": "sph2", "fromPort": 0, "toPort": 0},
                    {"from": "num100", "to": "sph2", "fromPort": 0, "toPort": 1},
                    {"from": "sph1", "to": "bool_op", "fromPort": 0, "toPort": 0},
                    {"from": "sph2", "to": "bool_op", "fromPort": 0, "toPort": 1}
                ]
            }

            print("\nSending optimized Native Boolean instructions to Dynamo...")
            req = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "execute_dynamo_instructions",
                    "arguments": {
                        "instructions": json.dumps(instructions)
                    }
                },
                "id": str(uuid.uuid4())
            }
            await websocket.send(json.dumps(req))
            resp = await websocket.recv()
            print(f"Result: {json.loads(resp).get('result')}")

    except Exception as e:
        print(f"[FAIL] Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
