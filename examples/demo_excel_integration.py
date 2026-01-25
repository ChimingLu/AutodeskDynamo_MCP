# -*- coding: utf-8 -*-
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def demo_excel_integration():
    """
    示範如何整合 Excel 匯入工作流。
    此範例展示如何從腳本庫載入 Excel 模板並在 Dynamo 中執行。
    """
    server_params = StdioServerParameters(
        command="node",
        args=["bridge/node/index.js"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 從腳本庫載入 Excel 模板
            print("读取 Excel 导入模板...")
            result = await session.call_tool(
                "execute_dynamo_instructions",
                arguments={"instructions": json.dumps({
                    "nodes": [
                        {"id": "path", "name": "Code Block", "value": "\"C:/Temp/data.xlsx\";", "x": 0, "y": 0},
                        {"id": "import", "name": "Code Block", "value": "Data.ImportExcel(path, \"Sheet1\", true, true);", "x": 300, "y": 0}
                    ],
                    "connectors": [{"from": "path", "to": "import", "fromPort": 0, "toPort": 0}]
                })}
            )
            
            if result.content:
                print(f"成功放置 Excel 節點: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(demo_excel_integration())
