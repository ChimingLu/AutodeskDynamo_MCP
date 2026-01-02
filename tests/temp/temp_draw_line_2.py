
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 繪製第二條線：平行於 Y 軸
                code_content = "p1 = Point.ByCoordinates(500, 0, 0);\np2 = Point.ByCoordinates(500, 1000, 0);\nl2 = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "line_v2",
                            "name": "Number",
                            "x": 0,
                            "y": 500,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Adding another line to the workspace...")
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
