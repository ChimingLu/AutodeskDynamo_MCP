
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 這次將名稱設為簡稱 "Code Block"
                # 正確的邏輯已經在 GraphHandler.cs 中將 "Number" 指向了 "Code Block"
                # 所以我們現在直接用 "Code Block" 試試看，並給予完整的多行語法
                code_content = "p1 = Point.ByCoordinates(0, 0, 0);\np2 = Point.ByCoordinates(100, 100, 0);\nl1 = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "cb_logic",
                            "name": "Code Block",
                            "x": 100,
                            "y": 100,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Final attempt: Drawing a line using a single Code Block node...")
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
