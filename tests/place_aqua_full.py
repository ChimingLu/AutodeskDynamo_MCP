
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Trying full name guessed from category
                instructions = {
                    "nodes": [
                        {"id": "aqua1", "name": "Clockwork.Display.Create.Color.Aqua", "x": 0, "y": 0}
                    ],
                    "connectors": []
                }
                
                print("Placing Clockwork 'Color.Aqua' node (FullName trial)...")
                result = await session.call_tool("execute_dynamo_instructions", arguments={"instructions": json.dumps(instructions)})
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
