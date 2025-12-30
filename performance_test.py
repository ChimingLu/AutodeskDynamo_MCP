"""
效能測試腳本 - 驗證節點搜尋的 Token 消耗與回應時間
"""

import asyncio
import json
import time
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def test_performance():
    print("=" * 60)
    print("Dynamo MCP 效能測試")
    print("=" * 60)
    
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            print("✓ 已連接到 MCP Server")
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 測試 1: Basic Detail (最小 Token)
                print("\n[測試 1] detail='basic' - 最小 Token 消耗")
                start_time = time.time()
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={"filter_text": "Point", "detail": "basic"}
                )
                elapsed = time.time() - start_time
                
                response_text = result.content[0].text
                response_size = len(response_text)
                data = json.loads(response_text)
                
                print(f"  - 回應時間: {elapsed:.3f} 秒")
                print(f"  - 回應大小: {response_size} bytes (~{response_size//4} tokens)")
                print(f"  - 節點數量: {data.get('count', 0)}")
                print(f"  - Common 節點: {data.get('commonCount', 0)}")
                print(f"  - Global 節點: {data.get('globalCount', 0)}")
                
                # 測試 2: Standard Detail
                print("\n[測試 2] detail='standard' - 中等 Token 消耗")
                start_time = time.time()
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={"filter_text": "Point", "detail": "standard"}
                )
                elapsed = time.time() - start_time
                
                response_text = result.content[0].text
                response_size = len(response_text)
                
                print(f"  - 回應時間: {elapsed:.3f} 秒")
                print(f"  - 回應大小: {response_size} bytes (~{response_size//4} tokens)")
                
                # 測試 3: Full Detail (最大 Token)
                print("\n[測試 3] detail='full' - 最大 Token 消耗")
                start_time = time.time()
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={"filter_text": "Point", "detail": "full"}
                )
                elapsed = time.time() - start_time
                
                response_text = result.content[0].text
                response_size = len(response_text)
                
                print(f"  - 回應時間: {elapsed:.3f} 秒")
                print(f"  - 回應大小: {response_size} bytes (~{response_size//4} tokens)")
                
                # 測試 4: 快取效能
                print("\n[測試 4] 快取效能測試 (重複查詢)")
                start_time = time.time()
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={"filter_text": "Point", "detail": "basic"}
                )
                elapsed = time.time() - start_time
                
                print(f"  - 快取回應時間: {elapsed:.3f} 秒")
                print(f"  - 預期: 應該明顯快於首次查詢")
                
                # 測試 5: Common Nodes 優先順序
                print("\n[測試 5] Common Nodes 優先順序驗證")
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={"filter_text": "Point", "detail": "basic"}
                )
                
                response_text = result.content[0].text
                data = json.loads(response_text)
                nodes = data.get('nodes', [])
                
                if nodes:
                    first_node = nodes[0]
                    is_common = first_node.get('isCommon', False)
                    print(f"  - 第一個節點: {first_node.get('name')}")
                    print(f"  - 是否為 Common Node: {'✓ 是' if is_common else '✗ 否'}")
                    
                    # 檢查所有 common nodes 是否在前面
                    common_indices = [i for i, n in enumerate(nodes) if n.get('isCommon')]
                    if common_indices:
                        print(f"  - Common Nodes 位置: {common_indices}")
                        if common_indices == list(range(len(common_indices))):
                            print("  - ✓ Common Nodes 確實排在最前面")
                        else:
                            print("  - ✗ 警告: Common Nodes 未正確排序")
                
                print("\n" + "=" * 60)
                print("測試完成！")
                print("=" * 60)
                
    except Exception as e:
        import traceback
        print(f"\n✗ 錯誤: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("\n請確保:")
    print("1. Dynamo 與 MCP Listener 已啟動 (Port 5050)")
    print("2. Python MCP Server 已啟動 (Port 8000)")
    print("\n按 Enter 開始測試...")
    input()
    
    asyncio.run(test_performance())
