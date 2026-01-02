
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 傳統節點組合方式
                instructions = {
                    "nodes": [
                        {"id": "p1", "name": "Point.ByCoordinates", "x": 0, "y": 0},
                        {"id": "p2", "name": "Point.ByCoordinates", "x": 100, "y": 100},
                        {"id": "line", "name": "Line.ByStartPointEndPoint", "x": 300, "y": 0}
                    ],
                    "connectors": [
                        {"from": "p1", "to": "line", "fromPort": 0, "toPort": 0},
                        {"from": "p2", "to": "line", "fromPort": 0, "toPort": 1}
                    ]
                }
                
                print("Executing line creation via standard nodes...")
                result = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={
                        "instructions": json.dumps(instructions),
                        "clear_before_execute": False
                    }
                )
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
