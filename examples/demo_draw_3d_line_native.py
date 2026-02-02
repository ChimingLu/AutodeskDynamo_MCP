#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用原生節點繪製 3D 線段示例

說明：
- 使用軌道 B（原生節點自動擴展）方式
- 自動創建 Point.ByCoordinates 和 Line.ByStartPointEndPoint 節點
- 線段連接起點 (0, 0, 0) 和終點 (100, 100, 100)
"""

import json
import asyncio
import websockets
import sys

async def draw_3d_line_native():
    """
    使用原生節點方式繪製 3D 線段
    """
    
    # MCP Bridge WebSocket 位址
    ws_url = "ws://127.0.0.1:65296"
    
    # 定義線段指令（軌道 B：原生節點 + params 參數化）
    instruction = {
        "nodes": [
            {
                "id": "start_pt",
                "name": "Point.ByCoordinates",
                "params": {
                    "x": 0,
                    "y": 0,
                    "z": 0
                },
                "overload": "3D",
                "preview": False,
                "x": 100,
                "y": 300
            },
            {
                "id": "end_pt",
                "name": "Point.ByCoordinates",
                "params": {
                    "x": 100,
                    "y": 100,
                    "z": 100
                },
                "overload": "3D",
                "preview": False,
                "x": 100,
                "y": 450
            },
            {
                "id": "line1",
                "name": "Line.ByStartPointEndPoint",
                "preview": True,
                "x": 500,
                "y": 375
            }
        ],
        "connectors": [
            {
                "from": "start_pt",
                "to": "line1",
                "fromPort": 0,
                "toPort": 0
            },
            {
                "from": "end_pt",
                "to": "line1",
                "fromPort": 0,
                "toPort": 1
            }
        ]
    }
    
    try:
        # 轉換為 JSON 字串（execute_dynamo_instructions 期望字串格式）
        json_str = json.dumps(instruction, ensure_ascii=False)
        
        print("正在連接 Dynamo...")
        print(f"指令: {json_str[:100]}...\n")
        
        # 發送指令通過 WebSocket
        async with websockets.connect(ws_url, ping_interval=None) as ws:
            # 準備 JSON-RPC 2.0 請求
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "execute_dynamo_instructions",
                    "arguments": {
                        "instructions": json_str,
                        "clear_before_execute": False,
                        "base_x": 0,
                        "base_y": 0,
                        "allow_fallback": True
                    }
                }
            }
            
            # 發送請求
            await ws.send(json.dumps(request))
            
            # 接收回應
            response = await asyncio.wait_for(ws.recv(), timeout=15.0)
            result = json.loads(response)
            
            if "result" in result:
                print("[OK] 操作完成!")
                print(f"回應: {result['result']}")
            else:
                print("[FAIL] 錯誤回應")
                print(f"回應: {result}")
            
    except ConnectionRefusedError:
        print("\n[FAIL] 無法連接 Dynamo MCP Server")
        print("請確認:")
        print("1. Python MCP Server 已啟動 (python bridge/python/server.py)")
        print("2. Dynamo 已開啟並連接 (BIM Assistant -> Connect)")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def main():
    await draw_3d_line_native()

if __name__ == "__main__":
    asyncio.run(main())
