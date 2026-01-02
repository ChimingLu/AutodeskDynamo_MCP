
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 使用 Number 作為捷點名稱（會被解析為 Code Block）
                # 這次繪製一個明顯的長度與座標
                code_content = "p1 = Point.ByCoordinates(0, 0, 0);\np2 = Point.ByCoordinates(1000, 1000, 0);\nl1 = Line.ByStartPointEndPoint(p1, p2);"
                
                instructions = {
                    "nodes": [
                        {
                            "id": "cb_line_final",
                            "name": "Number",
                            "x": 0,
                            "y": 0,
                            "value": code_content
                        }
                    ],
                    "connectors": []
                }
                
                print("Final Draw Attempt: Sending Code Block with Line logic...")
                # 我們不清除畫面，直接加上去，這樣畫面上應該會有剛才的 Watch 和這個 Code Block
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
