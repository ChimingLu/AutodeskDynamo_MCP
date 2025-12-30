
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
                
                # 1. 搜尋可用腳本
                print("1. Listing Library...")
                result_obj = await session.call_tool("get_script_library", arguments={})
                lib_str = result_obj.content[0].text
                library = json.loads(lib_str)
                print(f"   Found scripts: {[s['name'] for s in library]}")
                
                target_script = "solid_demo"
                
                # 2. 載入腳本
                print(f"2. Loading script '{target_script}'...")
                load_res = await session.call_tool("load_script_from_library", arguments={"name": target_script})
                content_json = load_res.content[0].text
                
                if "Error" in content_json:
                    print(f"   Failed to load: {content_json}")
                    return

                # 3. 執行腳本
                print(f"3. Executing '{target_script}'...")
                # content_json is already a JSON string of the graph definition
                result = await session.call_tool("execute_dynamo_instructions", arguments={"instructions": content_json})
                print(f"   Result: {result}")
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}") 
        if hasattr(e, '__cause__'):
             print(f"Cause: {e.__cause__}")
        if hasattr(e, 'exceptions'):
             print(f"Sub-exceptions: {e.exceptions}")

if __name__ == "__main__":
    asyncio.run(main())
