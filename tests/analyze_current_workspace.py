import sys
import json
import os
import asyncio

# Add parent directory to path to import server module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the MCP instance directly
from server import mcp

async def analyze_workspace():
    """獲取當前 Dynamo 工作區的完整分析"""
    try:
        # Call the analyze_workspace tool directly (async)
        result = await mcp.call_tool("analyze_workspace", {})
        
        # Parse and save output
        if isinstance(result, list) and len(result) > 0:
            content = result[0].text if hasattr(result[0], 'text') else str(result[0])
            data = json.loads(content)
            
            # Save to file for image generation
            output_file = os.path.join(os.path.dirname(__file__), "workspace_analysis.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"成功！已儲存至: {output_file}")
            print(f"工作區名稱: {data.get('workspaceName', 'N/A')}")
            print(f"節點數量: {data.get('nodeCount', 0)}")
            print(f"Session ID: {data.get('sessionId', 'N/A')}")
            return data
        else:
            print(f"錯誤: 未預期的回傳格式")
            return None
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(analyze_workspace())



