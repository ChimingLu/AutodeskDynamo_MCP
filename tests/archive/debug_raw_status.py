
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Analyzing workspace (RAW)...")
                # calling the tool returns a TextContent object
                result = await session.call_tool("analyze_workspace", arguments={})
                raw_text = result.content[0].text
                
                print(f"RAW JSON:\n{raw_text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
