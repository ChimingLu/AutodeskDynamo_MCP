
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                code_content = "p_start = Point.ByCoordinates(200, 200, 100);\np_end = Point.ByCoordinates(800, 800, 500);\nrandom_line = Line.ByStartPointEndPoint(p_start, p_end);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "random_line_cb",
                            "name": "Number",
                            "x": 300,
                            "y": 300,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Drawing a random 3D line...")
                result = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={
                        "instructions": json.dumps(instructions)
                    }
                )
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
