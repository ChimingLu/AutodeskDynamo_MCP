#!/usr/bin/env python3
import json
import asyncio
import websockets

# 定義 3D 點指令 (軌道 A: Code Block)
POINT_INSTRUCTION = {
    "nodes": [{
        "id": "pt_3d_test",
        "name": "Number",
        "value": "Point.ByCoordinates(10, 20, 30);",
        "x": 300,
        "y": 300
    }],
    "connectors": []
}

async def send_to_dynamo():
    uri = "ws://127.0.0.1:65535" # 直接連向 Dynamo ViewExtension
    try:
        async with websockets.connect(uri) as websocket:
            print(f"🚀 正在發送指令至 {uri}...")
            await websocket.send(json.dumps(POINT_INSTRUCTION))
            print("✅ 指令已送出：Point.ByCoordinates(10, 20, 30);")
            print("✨ 請查看 Dynamo 畫面。")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    asyncio.run(send_to_dynamo())
