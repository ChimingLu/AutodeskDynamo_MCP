
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 這次直接使用節點名稱 "Code Block"
                # 根據 GraphHandler.cs 第 497 行，這會進入專門處理 Code Block 的分支
                code_content = "p1 = Point.ByCoordinates(0, 0, 0);\np2 = Point.ByCoordinates(100, 100, 100);\nLine.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "cb1",
                            "name": "Code Block",
                            "x": 100,
                            "y": 100,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Executing line creation via Code Block (using name='Code Block')...")
                result = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={
                        "instructions": json.dumps(instructions),
                        "clear_before_execute": True
                    }
                )
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
