# Copyright 2026 ChimingLu.
# Licensed under the Apache License, Version 2.0

"""
分析當前 Dynamo 工作區的腳本

此腳本會：
1. 調用 MCP 的 analyze_workspace 工具
2. 解析回傳的 JSON 資料
3. 自動儲存至 tests/temp/workspace_analysis.json
4. 輸出工作區基本資訊

使用方式：
    python examples/analyze_current_workspace.py
"""

import sys
import json
import os
import asyncio

# 將專案根目錄加入路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接匯入 MCP 實例
from server import mcp


async def analyze_workspace():
    """分析當前 Dynamo 工作區"""
    try:
        # 直接調用 analyze_workspace 工具 (async)
        result = await mcp.call_tool("analyze_workspace", {})

        if result:
            # 處理 MCP 回傳的 CallToolResult 物件
            raw_str = str(result)
            
            # 策略 1: 提取 text=' ... ' 之間的內容
            content = raw_str
            if "text='" in raw_str:
                start = raw_str.find("text='") + 6
                end = raw_str.rfind("'", start)
                if end > start:
                    content = raw_str[start:end]
            
            # 策略 2: 如果是 list，取第一個元素的 text 屬性
            elif hasattr(result, '__iter__') and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    content = first_item.text
            
            # 策略 3: 直接存取 text 屬性
            elif hasattr(result, 'text'):
                content = result.text


            # 嘗試解析 JSON
            try:
                # 方法 1: 直接解析第一個 JSON 物件（處理 Extra data 問題）
                decoder = json.JSONDecoder()
                data, idx = decoder.raw_decode(content)

            except (json.JSONDecodeError, ValueError):
                # 方法 2: 處理雙反斜線並嘗試 Unicode 解碼
                try:
                    fixed_content = content.replace('\\\\', '\\')
                    decoder = json.JSONDecoder()
                    data, idx = decoder.raw_decode(fixed_content)
                    
                except (json.JSONDecodeError, ValueError):
                    # 方法 3: 處理 Unicode 轉義（如 \\u96e8）
                    try:
                        import codecs
                        decoded_content = codecs.decode(content, 'unicode_escape')
                        decoder = json.JSONDecoder()
                        data, idx = decoder.raw_decode(decoded_content)
                        
                    except Exception as final_error:
                        print(f"❌ 錯誤: 無法解析為有效的 JSON 格式")
                        print(f"原始內容預覽: {content[:200]}...")
                        print(f"錯誤訊息: {final_error}")
                        return None

            
            # 成功解析後的處理
            try:

                # 儲存至檔案
                output_file = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), 
                    "tests", 
                    "temp", 
                    "workspace_analysis.json"
                )
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                print(f"✅ 分析結果已儲存至: {output_file}")
                print(f"📄 工作區名稱: {data.get('workspaceName', 'N/A')}")
                print(f"🔢 節點數量: {data.get('nodeCount', 0)}")
                print(f"🔗 連線數量: {data.get('connectorCount', 0)}")
                
                return data
                
            except Exception as save_error:
                print(f"⚠️ 警告: 資料解析成功但儲存失敗 - {save_error}")
                return data
                
        else:
            print(f"❌ 錯誤: 工具未回傳任何資料")
            return None
            
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(analyze_workspace())
