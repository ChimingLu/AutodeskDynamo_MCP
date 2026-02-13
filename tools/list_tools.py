
import asyncio
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_client import list_tools

async def main():
    tools = await list_tools()
    if tools:
        print(tools)
    else:
        print("No tools found or error occurred.")

if __name__ == "__main__":
    asyncio.run(main())
