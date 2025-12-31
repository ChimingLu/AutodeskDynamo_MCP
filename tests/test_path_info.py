import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def main():
    print("連接到 MCP Server...")
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                print("\n=== 測試 get_script_library (查看路徑資訊) ===")
                result = await session.call_tool("get_script_library", arguments={})
                lib_data = json.loads(result.content[0].text)
                print(json.dumps(lib_data, indent=2, ensure_ascii=False))
                
                print("\n=== 測試 save_script_to_library (確認返回完整路徑) ===")
                test_script = {
                    "nodes": [
                        {"id": "test1", "name": "Number", "value": 42, "x": 0, "y": 0}
                    ],
                    "connectors": []
                }
                
                result = await session.call_tool(
                    "save_script_to_library",
                    arguments={
                        "name": "test_path_display",
                        "description": "測試路徑顯示功能",
                        "content_json": json.dumps(test_script)
                    }
                )
                print(result.content[0].text)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"錯誤: {e}")

if __name__ == "__main__":
    asyncio.run(main())
