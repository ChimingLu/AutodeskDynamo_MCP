
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 在 Dynamo MCP 邏輯中，Code Block 的內容是透過 "value" 屬性傳遞的
                # 而不是 properties.Code
                code_content = "p1 = Point.ByCoordinates(0, 0, 0);\np2 = Point.ByCoordinates(100, 100, 100);\nLine.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "cb_line",
                            "name": "Code Block",
                            "x": 100,
                            "y": 100,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Executing line creation via Code Block (using 'value' field)...")
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
