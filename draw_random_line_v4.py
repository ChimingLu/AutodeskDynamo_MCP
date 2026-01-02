
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import random

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Generate random coordinates
                x1, y1, z1 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                x2, y2, z2 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                
                print(f"Drawing line from ({x1}, {y1}, {z1}) to ({x2}, {y2}, {z2})...")
                
                code_content = f"p1 = Point.ByCoordinates({x1}, {y1}, {z1});\np2 = Point.ByCoordinates({x2}, {y2}, {z2});\nl_rand = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "random_line_v4",
                            "name": "Number",
                            "x": 300,
                            "y": 300,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                result = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={
                        "instructions": json.dumps(instructions),
                        "clear_before_execute": False
                    }
                )
                print(result.content[0].text)
                
                # Check status after drawing
                status = await session.call_tool("analyze_workspace", arguments={})
                print(f"Status: {status.content[0].text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
