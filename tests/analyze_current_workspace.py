import sys
import json
import os
import asyncio

# Add parent directory to path to import server module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the MCP instance directly
from server import mcp

import re

async def analyze_workspace():
    """獲取當前 Dynamo 工作區的完整分析"""
    try:
        # Call the analyze_workspace tool directly (async)
        result = await mcp.call_tool("analyze_workspace", {})
        
        if result:
            raw_str = str(result)
            # Try to handle common MCP string escapes
            content = raw_str
            if "text='" in content:
                # Find content between text=' and '
                start = content.find("text='") + 6
                end = content.rfind("'")
                if end > start:
                    content = content[start:end]
            
            # Final attempt to parse
            try:
                # Handle double backslashes which are common in escaped JSON strings
                fixed_content = content.replace('\\\\', '\\')
                data = json.loads(fixed_content)
                
                # Save to file
                output_file = os.path.join(os.path.dirname(__file__), "temp", "workspace_analysis.json")
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print(f"成功！已儲存至: {output_file}")
                print(f"工作區名稱: {data.get('workspaceName', 'N/A')}")
                return data
            except json.JSONDecodeError:
                # If it's a valid JSON but with escaped unicode, try one more time
                try:
                    data = json.loads(content.encode('utf-8').decode('unicode_escape'))
                    # (Success logic same as above)
                    output_file = os.path.join(os.path.dirname(__file__), "temp", "workspace_analysis.json")
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"成功 (轉義後)！已儲存至: {output_file}")
                    return data
                except:
                    print(f"錯誤: 回傳內容不是有效的 JSON 格式")
                    print(f"原始內容片段: {content[:200]}...")
                    return None
        else:
            print(f"錯誤: 工具未回傳任何內容")
            return None
    except Exception as e:
        print(f"錯誤: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(analyze_workspace())



