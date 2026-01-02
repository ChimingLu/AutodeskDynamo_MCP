
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Testing geometry creation with short names...")
                # 嘗試使用短名稱，看 Dynamo 是否能自行解析
                instructions = {
                    "nodes": [
                        {
                            "id": "p1",
                            "name": "Point.ByCoordinates",
                            "x": 0,
                            "y": 0,
                            "value": "0,0,0" # 注意：如果是 Point.ByCoordinates，value 可能沒用，但我們先試試
                        },
                        {
                            "id": "sphere",
                            "name": "Sphere.ByCenterPointRadius",
                            "x": 200,
                            "y": 0
                        }
                    ],
                    "connectors": [
                        {"from": "p1", "to": "sphere", "fromPort": 0, "toPort": 0}
                    ]
                }
                
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
