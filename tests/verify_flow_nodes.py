
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    print("Connecting to MCP Server...")
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            print("Connected to SSE.")
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                # Test 1: Search for ScopeIf
                print("\nChecking for 'ScopeIf'...")
                result = await session.call_tool("list_available_nodes", arguments={"filter_text": "ScopeIf"})
                print(f"Result: {result.content[0].text}")
                
                # Test 2: Search for List.Flatten
                print("\nChecking for 'List.Flatten'...")
                result = await session.call_tool("list_available_nodes", arguments={"filter_text": "List.Flatten"})
                print(f"Result: {result.content[0].text}")

                # Test 3: Search for Dictionary
                print("\nChecking for 'Dictionary'...")
                result = await session.call_tool("list_available_nodes", arguments={"filter_text": "Dictionary"})
                print(f"Result: {result.content[0].text}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
