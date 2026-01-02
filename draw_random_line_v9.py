
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
                
                # Sanity check connection
                status = await session.call_tool("analyze_workspace", arguments={})
                status_data = json.loads(status.content[0].text)
                print(f"Connected to PID: {status_data.get('processId')} | Session: {status_data.get('sessionId')}")
                
                # Generate random coordinates
                x1, y1, z1 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                x2, y2, z2 = random.randint(0, 1000), random.randint(0, 1000), random.randint(0, 500)
                
                print(f"Drawing random line v9 from ({x1}, {y1}, {z1}) to ({x2}, {y2}, {z2})...")
                
                code_content = f"p_start_9 = Point.ByCoordinates({x1}, {y1}, {z1});\np_end_9 = Point.ByCoordinates({x2}, {y2}, {z2});\nline_9 = Line.ByStartPointEndPoint(p_start_9, p_end_9);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "random_line_v9",
                            "name": "Number", 
                            "x": 500,
                            "y": 800,
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
