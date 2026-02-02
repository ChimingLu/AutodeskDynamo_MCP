"""
MCP 配置檔案自動轉換工具
功能：將 mcp_config.template.jsonc (帶註解) 轉換為 mcp_config.json (無註解)
"""
import json
import re
from pathlib import Path

def remove_comments(text):
    """移除 JSONC 註解"""
    # 移除單行註解 (// ...)
    text = re.sub(r'//.*', '', text)
    # 移除多行註解 (/* ... */)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)
    return text

def remove_trailing_commas(text):
    """移除尾隨逗號"""
    # 移除物件或陣列最後一個元素後的逗號
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text

def main():
    print("=" * 50)
    print("MCP 配置檔案轉換工具")
    print("=" * 50)
    
    # 定義路徑
    project_root = Path(__file__).parent.parent
    template_file = project_root / "mcp_config.template.jsonc"
    output_file = project_root / "mcp_config.json"
    
    # 檢查模板檔案
    if not template_file.exists():
        print(f"[FAIL] 錯誤：找不到模板檔案 {template_file}")
        return 1
    
    print(f"\n[1/3] 讀取配置模板: {template_file.name}")
    content = template_file.read_text(encoding='utf-8')
    
    print("[2/3] 移除註解...")
    content = remove_comments(content)
    content = remove_trailing_commas(content)
    
    print("[3/3] 驗證 JSON 格式...")
    try:
        # 解析並驗證 JSON
        json_obj = json.loads(content)
        
        # 格式化輸出
        formatted_json = json.dumps(json_obj, indent=4, ensure_ascii=False)
        
        # 寫入檔案
        output_file.write_text(formatted_json, encoding='utf-8')
        
        print(f"\n[OK] 成功生成: {output_file}")
        print("   - 已移除所有註解")
        print("   - JSON 格式驗證通過")
        
        print("\n" + "=" * 50)
        print("轉換完成！")
        print("=" * 50)
        return 0
        
    except json.JSONDecodeError as e:
        print(f"\n[FAIL] JSON 格式驗證失敗: {e}")
        print("請檢查模板檔案的 JSON 語法是否正確")
        return 1

if __name__ == "__main__":
    exit(main())
