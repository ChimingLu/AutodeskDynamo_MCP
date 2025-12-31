
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                instructions = {
                    "nodes": [
                        {"id": "aqua1", "name": "Aqua", "x": 100, "y": 100}
                    ],
                    "connectors": []
                }
                
                print("Placing Clockwork 'Aqua' node (Name trial)...")
                result = await session.call_tool("execute_dynamo_instructions", arguments={"instructions": json.dumps(instructions)})
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
