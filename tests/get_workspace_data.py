import sys
import json
import os
import asyncio

# Add parent directory to path to import server module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the analyze_workspace function directly
from server import analyze_workspace

async def main():
    """直接調用 analyze_workspace 函數"""
    try:
        # Call the function directly
        result = analyze_workspace()
        print(f"函數類型: {type(result)}")
        print(f"回傳內容:\n{result}")
        
        # Try to parse as JSON
        try:
            data = json.loads(result)
            
            # Save to file
            output_file = os.path.join(os.path.dirname(__file__), "workspace_analysis.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ 成功！已儲存至: {output_file}")
            print(f"📋 工作區名稱: {data.get('workspaceName', 'N/A')}")
            print(f"🔢 節點數量: {data.get('nodeCount', 0)}")
            print(f"🆔 Session ID: {data.get('sessionId', 'N/A')}")
            
            if 'nodes' in data:
                print(f"\n節點列表 ({len(data['nodes'])} 個):")
                for node in data['nodes'][:5]:  # Show first 5
                    print(f"  - {node.get('name', '?')} ({node.get('type', '?')})")
                if len(data['nodes']) > 5:
                    print(f"  ... 還有 {len(data['nodes']) - 5} 個節點")
                    
            return data
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析錯誤: {e}")
            print(f"原始內容: {result[:500]}")
            return None
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(main())
