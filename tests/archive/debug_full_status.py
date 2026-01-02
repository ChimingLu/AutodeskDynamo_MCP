
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Analyzing workspace...")
                result = await session.call_tool("analyze_workspace", arguments={})
                data = json.loads(result.content[0].text)
                
                print(f"Node Count: {data.get('nodeCount')}")
                if "nodes" in data:
                    for i, node in enumerate(data["nodes"]):
                        print(f"Node {i+1}: Name='{node.get('name')}', ID='{node.get('id')}'")
                        print(f"       Type='{node.get('type')}', CreationName='{node.get('creationName')}'")
                
                if "mcp_warning" in data:
                    print(f"WARNING FOUND: {data['mcp_warning']}")
                else:
                    print("No warning found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
