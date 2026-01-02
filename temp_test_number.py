
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # 嘗試建立單一個 Number 節點 (這是 Core.Input.Basic.DoubleInput)
                instructions = {
                    "nodes": [
                        {
                            "id": "num1",
                            "name": "Number",
                            "x": 0,
                            "y": 0,
                            "value": "10.0"
                        }
                    ],
                    "connectors": []
                }
                
                print("Trying to create a single Number node...")
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
