
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Retrieving full details for Point.ByCoordinates...")
                result = await session.call_tool(
                    "list_available_nodes", 
                    arguments={
                        "filter_text": "Point.ByCoordinates",
                        "search_scope": "all",
                        "detail": "full"
                    }
                )
                print(result.content[0].text)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
