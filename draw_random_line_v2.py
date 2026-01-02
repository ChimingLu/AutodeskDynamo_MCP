
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 繪製一個新的隨機 3D 向量
                code_content = "start_p = Point.ByCoordinates(0, 500, 200);\nend_p = Point.ByCoordinates(1000, 500, 800);\nl_new = Line.ByStartPointEndPoint(start_p, end_p);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "new_random_line",
                            "name": "Number",
                            "x": 400,
                            "y": 400,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Adding another random line...")
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
