# Copyright 2026 ChimingLu.
# Licensed under the Apache License, Version 2.0

"""
分析當前 Dynamo 工作區的腳本

此腳本會：
1. 連線至 MCP Bridge Server (ws://127.0.0.1:65296)
2. 調用 analyze_workspace 工具 via JSON-RPC
3. 解析回傳的 JSON 資料
4. 自動儲存至 tests/temp/workspace_analysis.json
5. 輸出工作區基本資訊

使用方式：
    python examples/analyze_current_workspace.py
"""

import sys
import json
import os
import asyncio
import websockets

async def call_mcp_tool(tool_name, args={}):
    """透過 WebSocket 調用 MCP 工具"""
    uri = "ws://127.0.0.1:65296"
    try:
        async with websockets.connect(uri) as websocket:
            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": args
                },
                "id": 1
            }
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            data = json.loads(response)
            
            if "error" in data:
                print(f"[FAIL] JSON-RPC 錯誤: {data['error']}")
                return None
                
            return data.get("result")
    except ConnectionRefusedError:
        print("[FAIL] 連線失敗: 無法連線至 MCP 伺服器 (ws://127.0.0.1:65296)")
        print("[TIP] 請確認 server.py 是否正在執行。")
        return None
    except Exception as e:
        print(f"[FAIL] 通訊錯誤: {e}")
        return None

async def analyze_workspace():
    """分析當前 Dynamo 工作區"""
    print("[SEARCH] 正在連線至 MCP 伺服器...")
    
    # 調用 analyze_workspace 工具
    result = await call_mcp_tool("analyze_workspace", {})

    if not result:
        return # 錯誤已在 call_mcp_tool 輸出

    try:
        # 處理結果
        # result 應該是 JSON 字串 (根據 server.py implementation)
        # 或者包含錯誤訊息的字串
        
        content = str(result)
        
        # 簡單判斷是否為錯誤訊息
        if content.startswith("[FAIL]"):
             print(f"[WARNING] 工具回傳錯誤: {content}")
             # 仍嘗試解析以防它是 JSON
        
        data = None
        
        # 嘗試解析 JSON
        try:
            # 方法 1: 直接解析
            decoder = json.JSONDecoder()
            data, idx = decoder.raw_decode(content)

        except (json.JSONDecodeError, ValueError):
            # 方法 2: 處理雙反斜線並嘗試 Unicode 解碼
            try:
                fixed_content = content.replace('\\\\', '\\')
                decoder = json.JSONDecoder()
                data, idx = decoder.raw_decode(fixed_content)
                
            except (json.JSONDecodeError, ValueError):
                # 方法 3: 處理 Unicode 轉義（如 \\u96e8）
                try:
                    import codecs
                    decoded_content = codecs.decode(content, 'unicode_escape')
                    decoder = json.JSONDecoder()
                    data, idx = decoder.raw_decode(decoded_content)
                    
                except Exception as final_error:
                    # 若不是 JSON，可能就是純文字訊息
                    if "[FAIL]" in content:
                         return # 已印出錯誤
                    
                    print(f"[FAIL] 錯誤: 無法解析為有效的 JSON 格式")
                    print(f"原始內容預覽: {content[:200]}...")
                    return None

        # 成功解析後的處理
        try:
            # 儲存至檔案
            output_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "tests", 
                "temp", 
                "workspace_analysis.json"
            )
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"[OK] 分析結果已儲存至: {output_file}")
            
            # Print Summary
            ws_name = data.get('workspaceName', 'N/A')
            node_count = data.get('nodeCount', 0)
            
            print(f"[FILE] 工作區名稱: {ws_name}")
            print(f"[COUNT] 節點數量: {node_count}")
            print(f"🔗 連線數量: {data.get('connectorCount', 0)}")
            
            # Check for warnings
            if "mcp_warning" in data:
                print(f"⚠️ {data['mcp_warning']}")
            
            if "mcp_restart_warning" in data:
                 print(f"🔄 {data['mcp_restart_warning']}")

            return data
            
        except Exception as save_error:
            print(f"⚠️ 警告: 資料解析成功但儲存失敗 - {save_error}")
            return data
            
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(analyze_workspace())
