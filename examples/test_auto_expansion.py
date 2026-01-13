#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試自動擴展邏輯的完整流程
"""

from server import execute_dynamo_instructions, _load_common_nodes_metadata, route_node_creation
import json

# 模擬一個簡單的指令
instructions = {
    "nodes": [
        {
            "id": "cube",
            "name": "Cuboid.ByLengths",
            "params": {"width": 500, "length": 500, "height": 500},
            "x": 400,
            "y": 100,
            "preview": False
        }
    ],
    "connectors": []
}

print("=== 原始指令 ===")
print(json.dumps(instructions, indent=2, ensure_ascii=False))

# 手動模擬擴展流程
metadata = _load_common_nodes_metadata()
expanded_nodes = []
expanded_connectors = []

for node in instructions["nodes"]:
    # 路由處理
    route_node_creation(node)
    expanded_nodes.append(node)
    
    print(f"\n=== 處理節點: {node['name']} ===")
    print(f"Strategy: {node.get('_strategy')}")
    print(f"Params: {node.get('params')}")
    print(f"Node ID: {node.get('id')}")
    
    # 擴展邏輯
    strategy = node.get("_strategy", "")
    params = node.get("params", {})
    node_id = node.get("id")
    
    should_expand = (strategy in ["NATIVE_DIRECT", "NATIVE_WITH_OVERLOAD"]) and params and node_id
    print(f"Should Expand: {should_expand}")
    
    if should_expand:
        node_name = node.get("name")
        node_info = metadata.get(node_name, {})
        input_ports = node_info.get("inputs", [])
        
        print(f"Input Ports: {input_ports}")
        
        for i, port_name in enumerate(input_ports):
            if port_name in params:
                val = params[port_name]
                param_node_id = f"{node_id}_{port_name}_test"
                
                param_node = {
                    "id": param_node_id,
                    "name": "Number",
                    "value": str(val),
                    "x": node.get("x", 0) - 200,
                    "y": node.get("y", 0) + (i * 80),
                    "_strategy": "CODE_BLOCK",
                    "preview": node.get("preview", True)
                }
                
                print(f"  生成輔助節點: {param_node_id} = {val}")
                expanded_nodes.append(param_node)
                
                connector = {
                    "from": param_node_id,
                    "to": node_id,
                    "fromPort": 0,
                    "toPort": i
                }
                print(f"  生成連線: {param_node_id} -> {node_id} (port {i})")
                expanded_connectors.append(connector)

print("\n\n=== 擴展後的完整 JSON ===")
result = {
    "nodes": expanded_nodes,
    "connectors": expanded_connectors
}
print(json.dumps(result, indent=2, ensure_ascii=False))
