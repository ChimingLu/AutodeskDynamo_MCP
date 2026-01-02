
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
                
                # Check connection and print Session ID
                status = await session.call_tool("analyze_workspace", arguments={})
                status_data = json.loads(status.content[0].text)
                print(f"Connected to PID: {status_data.get('processId')} | Session: {status_data.get('sessionId')}")
                
                # Generate random coordinates
                x1, y1, z1 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                x2, y2, z2 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                
                print(f"Drawing random line v7 from ({x1}, {y1}, {z1}) to ({x2}, {y2}, {z2})...")
                
                code_content = f"point_A = Point.ByCoordinates({x1}, {y1}, {z1});\npoint_B = Point.ByCoordinates({x2}, {y2}, {z2});\nline_random = Line.ByStartPointEndPoint(point_A, point_B);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "random_line_v7",
                            "name": "Number",
                            "x": 500,
                            "y": 200,
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
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
