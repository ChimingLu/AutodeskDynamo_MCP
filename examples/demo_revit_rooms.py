# -*- coding: utf-8 -*-
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def demo_revit_rooms():
    """
    示範如何使用 Python 腳本讀取 Revit 房間資訊。
    """
    server_params = StdioServerParameters(
        command="node",
        args=["bridge/node/index.js"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 建立帶有 Revit API 代碼的 Python 節點
            python_script = (
                "import clr\n"
                "clr.AddReference('RevitAPI')\n"
                "from Autodesk.Revit.DB import *\n"
                "clr.AddReference('RevitServices')\n"
                "from RevitServices.Persistence import DocumentManager\n\n"
                "doc = DocumentManager.Instance.CurrentDBDocument\n"
                "collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()\n\n"
                "OUT = [r.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() for r in collector]"
            )
            
            instructions = {
                "nodes": [
                    {
                        "id": "room_node",
                        "name": "Python Script",
                        "script": python_script,
                        "x": 100,
                        "y": 100
                    }
                ]
            }
            
            print("正在建立 Revit 房間收集器...")
            result = await session.call_tool(
                "execute_dynamo_instructions",
                arguments={"instructions": json.dumps(instructions)}
            )
            
            if result.content:
                print(f"執行結果: {result.content[0].text}")

if __name__ == "__main__":
    asyncio.run(demo_revit_rooms())
