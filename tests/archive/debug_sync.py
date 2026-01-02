
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("--- Stage 1: Clearing Workspace ---")
                clear_res = await session.call_tool("clear_workspace", arguments={})
                print(f"Clear Result: {clear_res.content[0].text}")
                
                print("--- Stage 2: Initial Status Check ---")
                status1 = await session.call_tool("analyze_workspace", arguments={})
                print(f"Status After Clear: {status1.content[0].text}")
                
                print("--- Stage 3: Placing a 'Watch' Node ---")
                # 使用 Watch 節點作為最簡單的測試，因為它不涉及模型執行邏輯
                instructions = {
                    "nodes": [
                        {
                            "id": "visual_test",
                            "name": "Watch",
                            "x": 200,
                            "y": 200
                        }
                    ],
                    "connectors": []
                }
                place_res = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={"instructions": json.dumps(instructions)}
                )
                print(f"Place Result: {place_res.content[0].text}")
                
                print("--- Stage 4: Final Status Check ---")
                status2 = await session.call_tool("analyze_workspace", arguments={})
                print(f"Final Status: {status2.content[0].text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
