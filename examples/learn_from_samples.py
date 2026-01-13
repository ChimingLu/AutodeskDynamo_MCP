import json
import os
import glob

def extract_nodes_from_dyn(file_path):
    nodes_info = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        nodes = data.get("Nodes", []) or data.get("NodeModels", [])
        
        for node in nodes:
            name = node.get("Name")
            # 在新版 DYN 中，完整簽名通常在 FunctionSignature 
            full_name = node.get("FunctionSignature") or node.get("CreationName")
            
            if not full_name:
                continue
            
            # 如果沒有 inputs 埠位資訊，嘗試從不同的欄位提取
            inputs = []
            in_ports = node.get("Inputs") or node.get("InPorts") or []
            for port in in_ports:
                # 埠位名稱可能在 Name, NickName 或甚至是 ToolTip
                p_name = port.get("Name") or port.get("NickName")
                if p_name:
                    inputs.append(p_name)

            if full_name not in nodes_info:
                nodes_info[full_name] = {
                    "name": name,
                    "fullName": full_name,
                    "inputs": inputs,
                    "type": node.get("ConcreteType", "Unknown")
                }
    except Exception as e:
        print(f"Error parse: {e}")
    
    return nodes_info

def main():
    root_dir = r"d:\AI\An\AutodeskDynamo_MCP\tests\samples"
    all_knowledge = {}
    
    dyn_files = glob.glob(os.path.join(root_dir, "**", "*.dyn"), recursive=True)
    print(f"找到 {len(dyn_files)} 個 DYN 檔案。開始學習...")
    
    for file in dyn_files:
        nodes = extract_nodes_from_dyn(file)
        all_knowledge.update(nodes)

    print(f"學習完成！總共學到了 {len(all_knowledge)} 個獨特的節點定義。")
    
    output_path = r"d:\AI\An\AutodeskDynamo_MCP\image\dynamo_knowledge_base.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(list(all_knowledge.values()), f, indent=4, ensure_ascii=False)
    
    print(f"知識庫已更新至: {output_path}")

if __name__ == "__main__":
    main()
