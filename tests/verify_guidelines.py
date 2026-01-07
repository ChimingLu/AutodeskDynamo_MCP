
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("Calling get_mcp_guidelines...")
                result = await session.call_tool("get_mcp_guidelines", arguments={})
                content = result.content[0].text
                
                if "# MCP GUIDELINES" in content and "# QUICK REFERENCE" in content:
                    print("✅ Verification Success: Guidelines received.")
                    print("Sample content:")
                    print(content[:200] + "...")
                else:
                    print("❌ Verification Failed: Content mismatch.")
                    print(content[:500])

    except Exception as e:
        print(f"❌ Verification Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
