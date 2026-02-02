import json
import os

def main():
    base_file = r"d:\AI\An\AutodeskDynamo_MCP\DynamoViewExtension\common_nodes.json"
    learned_file = r"d:\AI\An\AutodeskDynamo_MCP\image\dynamo_knowledge_base.json"
    
    # 載入現有資料
    with open(base_file, 'r', encoding='utf-8') as f:
        common_nodes = json.load(f)
    
    # 建立目前 FullName 的索引
    existing_fullnames = {node["fullName"]: i for i, node in enumerate(common_nodes)}
    # 建立簡稱 (Point.ByCoordinates) 的索引，方便匹配
    existing_shortnames = {node["name"]: i for i, node in enumerate(common_nodes) if "name" in node}
    
    # 載入學到的知識
    with open(learned_file, 'r', encoding='utf-8') as f:
        learned_data = json.load(f)
            
    added_count = 0
    updated_count = 0
    
    for item in learned_data:
        full_name = item["fullName"]
        inputs = item["inputs"]
        # 從 FullName 提取簡稱 (例如 Autodesk.Geometry.Point.ByCoordinates@... -> Point.ByCoordinates)
        short_name = full_name.split('@')[0].split('.')[-1]
        if '.' in full_name.split('@')[0]:
            parts = full_name.split('@')[0].split('.')
            if len(parts) >= 2:
                short_name = f"{parts[-2]}.{parts[-1]}"
        
        # 1. 如果 FullName 已存在，補完 inputs
        if full_name in existing_fullnames:
            idx = existing_fullnames[full_name]
            if not common_nodes[idx].get("inputs") or len(common_nodes[idx]["inputs"]) < len(inputs):
                common_nodes[idx]["inputs"] = inputs
                updated_count += 1
        
        # 2. 如果 ShortName 存在但 FullName 不同，且目前沒有設定 Overload
        elif short_name in existing_shortnames:
            idx = existing_shortnames[short_name]
            # 只有在目前不是 Overload 模式且 FullName 變更時才更新
            if common_nodes[idx].get("creationStrategy") != "NATIVE_WITH_OVERLOAD":
                # 我們保留原本的 name，但補強 fullName 和 inputs
                # (暫不自動修改，避免破壞手動配置)
                pass
        
        # 3. 如果是全新節點，直接加入
        else:
            new_node = {
                "name": short_name,
                "fullName": full_name,
                "creationStrategy": "NATIVE_DIRECT",
                "inputs": inputs,
                "description": f"Learned from official sample: {item.get('type', 'DSFunction')}"
            }
            common_nodes.append(new_node)
            added_count += 1

    # 儲存更新後的檔案
    with open(base_file, 'w', encoding='utf-8') as f:
        json.dump(common_nodes, f, indent=4, ensure_ascii=False)
        
    print(f"[OK] 升級完成！")
    print(f"[STATS] 新增節點: {added_count}")
    print(f"[STATS] 補完資訊: {updated_count}")
    print(f"💾 已儲存至: {base_file}")

if __name__ == "__main__":
    main()
