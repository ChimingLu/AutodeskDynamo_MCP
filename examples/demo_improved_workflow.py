#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
改进的工作流程：优先查询脚本库
遵循 GEMINI.md 核心教训 #5：腳本庫復用優先於重新生成
"""

import json
import os
import glob

def search_script_library(query: str) -> dict:
    """
    搜索脚本库，查找相关脚本
    
    Args:
        query: 搜索关键字（如 "line", "3d", "random" 等）
    
    Returns:
        匹配的脚本列表
    """
    script_dir = 'DynamoScripts'
    results = []
    
    # 查询所有 JSON 脚本
    for script_file in glob.glob(os.path.join(script_dir, '*.json')):
        if 'temp' in script_file:
            continue
            
        script_name = os.path.basename(script_file).replace('.json', '')
        
        try:
            with open(script_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
                description = content.get('description', '')
                
                # 模糊匹配
                if query.lower() in script_name.lower() or query.lower() in description.lower():
                    results.append({
                        'name': script_name,
                        'description': description,
                        'file': script_file,
                        'content': content
                    })
        except:
            pass
    
    return results

def load_script(script_name: str) -> dict:
    """
    加载脚本库中的脚本
    
    Args:
        script_name: 脚本名称（不含 .json）
    
    Returns:
        脚本内容
    """
    script_file = os.path.join('DynamoScripts', f'{script_name}.json')
    
    if not os.path.exists(script_file):
        return None
    
    with open(script_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def apply_script_with_parameters(script: dict, **kwargs) -> dict:
    """
    使用参数应用脚本模板
    
    Args:
        script: 脚本内容
        **kwargs: 参数（如 x1=0, y1=0, z1=0 等）
    
    Returns:
        参数替换后的脚本
    """
    import copy
    result = copy.deepcopy(script)
    
    # 替换所有占位符
    script_str = json.dumps(result)
    for key, value in kwargs.items():
        placeholder = f"{{{key}}}"
        script_str = script_str.replace(placeholder, str(value))
    
    return json.loads(script_str)

# ============================================================
# 演示：绘制 3D 线段
# ============================================================

print("🎯 改进的工作流程：优先查询脚本库")
print("=" * 70)
print()

# 第一步：查询脚本库
print("📖 第一步：查询脚本库...")
print()

query = "line"
matches = search_script_library(query)

print(f"🔍 搜索关键字：'{query}'")
print(f"📊 找到 {len(matches)} 个匹配的脚本：")
print()

for i, match in enumerate(matches, 1):
    print(f"{i}. {match['name']}")
    print(f"   描述：{match['description']}")
    print()

# 第二步：选择合适的脚本
print("=" * 70)
print("📚 第二步：选择合适的脚本...")
print()

# 对于 3D 线段，random_line.json 是最佳选择
selected_script = 'random_line'
print(f"✅ 选择脚本：{selected_script}")
print()

# 第三步：加载脚本
print("=" * 70)
print("📥 第三步：加载脚本...")
print()

script = load_script(selected_script)
print(f"✅ 脚本已加载")
print(f"   描述：{script.get('description')}")
print()

# 第四步：应用参数（如有必要）
print("=" * 70)
print("⚙️  第四步：应用参数...")
print()

# 为了演示，使用自定义坐标
parameters = {
    'x1': 0,
    'y1': 0,
    'z1': 0,
    'x2': 100,
    'y2': 100,
    'z2': 150
}

result = apply_script_with_parameters(script, **parameters)

print(f"参数配置：")
for key, value in parameters.items():
    print(f"  • {key} = {value}")
print()

# 第五步：显示最终指令
print("=" * 70)
print("📋 第五步：最终指令")
print()

print("JSON 指令（准备发送给 Dynamo）：")
print(json.dumps(result['content'], indent=2, ensure_ascii=False))
print()

print("✅ 工作流程完成！")
print()
print("💡 优势：")
print("   ✓ 使用已验证的稳定脚本")
print("   ✓ 支持参数化定制")
print("   ✓ 符合项目规范（脚本库优先）")
print("   ✓ 减少重复开发")
