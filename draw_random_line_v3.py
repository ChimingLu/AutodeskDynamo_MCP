
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 繪製第三個隨機 3D 線段：垂直分佈
                code_content = "pa = Point.ByCoordinates(500, 500, 0);\npb = Point.ByCoordinates(500, 500, 1500);\nl_vert = Line.ByStartPointEndPoint(pa, pb);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "random_line_3",
                            "name": "Number",
                            "x": 400,
                            "y": 800,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Adding a vertical random line...")
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
