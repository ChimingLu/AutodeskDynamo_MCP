
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 使用 "Number" 作為節點名稱，但內容寫入多行 DesignScript
                # 這是目前已知唯一能成功觸發 CreateNodeCommand("Code Block") 的路徑
                code_content = "p1 = Point.ByCoordinates(0, 0, 0);\np2 = Point.ByCoordinates(100, 100, 0);\nl1 = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "cb_logic",
                            "name": "Number",
                            "x": 100,
                            "y": 100,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Special trick: Using 'Number' name to create a Code Block with line logic...")
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
