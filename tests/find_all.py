
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Listing all nodes (first 100)...")
                # Using a larger limit if possible, but the server has a limit of 200 for 'all'
                result = await session.call_tool("list_available_nodes", arguments={"filter_text": "", "search_scope": "all"})
                data = json.loads(result.content[0].text)
                print(f"Total count: {data['count']}")
                for node in data.get("nodes", []):
                    if "Clockwork" in node.get("fullName", "") or "Aqua" in node.get("name", ""):
                         print(f"Found: {node['name']} ({node['fullName']})")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
