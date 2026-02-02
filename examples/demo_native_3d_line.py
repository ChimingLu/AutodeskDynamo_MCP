#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用原生節點繪製 3D 線段 - 直接調用方式

說明：
- 使用軌道 B（原生節點自動擴展）方式
- 定義起點 (0, 0, 0) 和終點 (100, 100, 100) 的 3D 線段
"""

import json
import sys
import os

# 添加 bridge 路徑
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bridge', 'python'))

def draw_3d_line_with_native_nodes():
    """
    使用原生節點方式繪製 3D 線段
    """
    
    # 定義線段指令（軌道 B：原生節點 + params 參數化）
    instruction = {
        "nodes": [
            {
                "id": "start_pt",
                "name": "Point.ByCoordinates",
                "params": {
                    "x": 0,
                    "y": 0,
                    "z": 0
                },
                "overload": "3D",
                "preview": False,
                "x": 100,
                "y": 300
            },
            {
                "id": "end_pt",
                "name": "Point.ByCoordinates",
                "params": {
                    "x": 100,
                    "y": 100,
                    "z": 100
                },
                "overload": "3D",
                "preview": False,
                "x": 100,
                "y": 450
            },
            {
                "id": "line1",
                "name": "Line.ByStartPointEndPoint",
                "preview": True,
                "x": 500,
                "y": 375
            }
        ],
        "connectors": [
            {
                "from": "start_pt",
                "to": "line1",
                "fromPort": 0,
                "toPort": 0,
                "toPortName": "startPoint"
            },
            {
                "from": "end_pt",
                "to": "line1",
                "fromPort": 0,
                "toPort": 1,
                "toPortName": "endPoint"
            }
        ]
    }
    
    print("=" * 60)
    print("使用原生節點繪製 3D 線段")
    print("=" * 60)
    print()
    print("指令詳情:")
    print("-" * 60)
    print("節點:")
    print(f"  1. 起點: Point.ByCoordinates(0, 0, 0)")
    print(f"  2. 終點: Point.ByCoordinates(100, 100, 100)")
    print(f"  3. 線段: Line.ByStartPointEndPoint(起點 -> 終點)")
    print()
    print("連線:")
    print(f"  - 起點.output[0] -> 線段.input[0] (startPoint)")
    print(f"  - 終點.output[0] -> 線段.input[1] (endPoint)")
    print("-" * 60)
    print()
    
    # 將指令轉換為 JSON 字串
    json_str = json.dumps(instruction, ensure_ascii=False, indent=2)
    
    # 儲存指令到文件便於查看
    output_file = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'DynamoScripts', 
        'temp', 
        'line_3d_native.json'
    )
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(json_str)
    
    print(f"[OK] 指令已保存至: {output_file}")
    print()
    print("JSON 指令:")
    print("-" * 60)
    print(json_str)
    print("-" * 60)
    print()
    print("使用方法:")
    print("  1. 確保 Python MCP Server 已啟動")
    print("  2. 確保 Dynamo 已開啟並連接")
    print("  3. 在 Gemini/Claude 中使用以下指令:")
    print()
    print(f'     execute_dynamo_instructions(\'{json_str}\')')
    print()
    print("或使用 examples 中的其他演示腳本")

if __name__ == "__main__":
    draw_3d_line_with_native_nodes()
