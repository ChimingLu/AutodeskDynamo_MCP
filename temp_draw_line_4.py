
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 繪製第四條線：Y=200 橫線
                code_content = "p1 = Point.ByCoordinates(0, 200, 0);\np2 = Point.ByCoordinates(1000, 200, 0);\nl4 = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "line_v4_unique",
                            "name": "Number",
                            "x": 200,
                            "y": 1500,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Adding a fourth line...")
                result = await session.call_tool(
                    "execute_dynamo_instructions", 
                    arguments={
                        "instructions": json.dumps(instructions),
                        "clear_before_execute": False
                    }
                )
                print(result.content[0].text)
                
                # 立即檢查數量
                status = await session.call_tool("analyze_workspace", arguments={})
                print(f"Current Node Count: {json.loads(status.content[0].text)['nodeCount']}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
