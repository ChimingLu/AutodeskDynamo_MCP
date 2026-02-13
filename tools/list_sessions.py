
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_client import call_tool

async def main():
    result = await call_tool("list_sessions")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
