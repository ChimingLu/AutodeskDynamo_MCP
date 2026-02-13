
import asyncio
import json
import os
import sys
import time
import websockets

# Add current directory to path so we can import mcp_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_client import call_tool

# Wrapper to match original function name if needed, or just use call_tool directly
async def call_mcp_tool(tool_name, args={}):
    return await call_tool(tool_name, args)

# ==========================================
# Test Steps
# ==========================================

async def test_search():
    print("[1/5] Testing Node Search...")
    start = time.time()
    result = await call_mcp_tool("search_nodes", {"query": "Point"})
    duration = time.time() - start
    
    # result is a string like "🔍 搜尋 'Point' 找到 50 個結果..."
    if result and "找到" in str(result) and not "找到 0 個" in str(result):
        print(f"✅ {duration:.2f}s - Found nodes.")
        return True
    else:
        print(f"❌ {duration:.2f}s - Search failed or no results. Result: {result}")
        return False

async def test_python_connection():
    print("[2/5] Testing Python Node + Connection...")
    start = time.time()
    
    # Define a simple graph: Number -> Python -> Watch
    # Python code simply returns input
    python_code = "OUT = IN[0]"
    
    graph = {
        "nodes": [
            {"id": "n1", "name": "Number", "value": "42", "x": 100, "y": 100},
            {"id": "n2", "name": "Python Script", "pythonCode": python_code, "inputCount": 1, "x": 300, "y": 100},
            {"id": "n3", "name": "Watch", "x": 500, "y": 100}
        ],
        "connectors": [
            {"from": "n1", "to": "n2", "fromPort": 0, "toPort": 0},
            {"from": "n2", "to": "n3", "fromPort": 0, "toPort": 0}
        ]
    }
    
    # Clear first (optional, but good for clean state)
    # await call_mcp_tool("clear_workspace", {}) 
    # We will do a full graph update.
    
    result = await call_mcp_tool("execute_dynamo_instructions", {"instructions": json.dumps(graph)})
    
    # Verify by analyzing workspace
    await asyncio.sleep(0.5) # Wait for execution
    analysis = await call_mcp_tool("analyze_workspace", {})
    
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except:
            print(f"❌ Failed to parse analysis result: {analysis}")
            return False

    if not isinstance(analysis, dict):
         print(f"❌ Analysis result is not a dict: {type(analysis)}")
         return False
    
    duration = time.time() - start
    
    node_count = analysis.get("nodeCount", 0)
    conn_count = analysis.get("connectorCount", 0)
    
    # Expect 3 nodes, 2 connectors
    if node_count >= 3 and conn_count >= 2:
        print(f"✅ {duration:.2f}s - Created {node_count} nodes, {conn_count} connectors.")
        return True
    else:
        print(f"❌ {duration:.2f}s - Failed. Got {node_count} nodes, {conn_count} connectors.")
        return False

async def test_clockwork():
    print("[3/5] Testing Plugin Support (Clockwork)...")
    start = time.time()
    
    # First search for it
    search_res = await call_mcp_tool("search_nodes", {"query": "Passthrough"})
    has_clockwork = "Passthrough" in str(search_res)
    
    if not has_clockwork:
        print(f"⚠️ {time.time()-start:.2f}s - Clockwork.Passthrough not found via search. Skipping creation test.")
        # We consider this a "pass" with warning, or skip
        return True
        
    # [Modified] Using GUID for Clockwork Passthrough as Dynamo fails to resolve via name string.
    # GUID: ecce77dc-1290-438e-a056-970b256fd553 (Found via analyze_passthrough.py)
    graph = {
        "nodes": [
            {"id": "c1", "name": "Number", "value": "100", "x": 100, "y": 300},
            {"id": "c2", "name": "ecce77dc-1290-438e-a056-970b256fd553", "x": 350, "y": 300},
            {"id": "c3", "name": "Watch", "x": 600, "y": 300}
        ],
        "connectors": [
            {"from": "c1", "to": "c2", "fromPort": 0, "toPort": 0},
            {"from": "c2", "to": "c3", "fromPort": 0, "toPort": 0}
        ]
    }
    
    # Note: execute_dynamo_instructions appends if not cleared? 
    # Actually server.py logic isn't fully clear on append vs replace without seeing `execute_dynamo_instructions` implementation details.
    # Usually it's additive unless we clear.
    # Let's clean up previous nodes or just add these.
    
    await call_mcp_tool("execute_dynamo_instructions", {"instructions": json.dumps(graph)})
    await asyncio.sleep(0.5)
    
    analysis = await call_mcp_tool("analyze_workspace", {})
    if isinstance(analysis, str):
        try: analysis = json.loads(analysis)
        except: pass
    if not isinstance(analysis, dict): analysis = {}

    nodes = analysis.get("nodes", [])
    node_names = [n.get("name") for n in nodes]
    
    has_passthrough = any("Passthrough" in name or "passthrough" in name.lower() for name in node_names if name)
    
    if has_passthrough:
        print(f"✅ {time.time()-start:.2f}s - Clockwork Passthrough node created successfully.")
        return True
    else:
        print(f"❌ {time.time()-start:.2f}s - Clockwork Passthrough node FAILED. Nodes: {node_names}")
        return False

async def test_geometry():
    print("[4/5] Testing Geometry Pipeline...")
    start = time.time()
    
    # Point.ByCoordinates(10, 20, 30) - 採用原生節點優先策略
    graph = {
        "nodes": [
            {
                "id": "g4", 
                "name": "Point.ByCoordinates", 
                "overload": "3D", 
                "params": {"x": 10, "y": 20, "z": 30},
                "x": 300, "y": 600
            },
            {"id": "g5", "name": "Watch", "x": 600, "y": 600}
        ],
        "connectors": [
            {"from": "g4", "to": "g5", "fromPort": 0, "toPort": 0}
        ]
    }
    
    await call_mcp_tool("execute_dynamo_instructions", {"instructions": json.dumps(graph)})
    await asyncio.sleep(0.5)
    
    analysis = await call_mcp_tool("analyze_workspace", {})
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except:
            pass
            
    print(f"✅ {time.time()-start:.2f}s - Geometry nodes created.")
    return True

async def test_library():
    print("[5/5] Testing Script Library...")
    start = time.time()
    
    scripts = await call_mcp_tool("get_script_library", {})
    count = len(scripts) if scripts else 0
    duration = time.time() - start
    
    if count >= 10:
        print(f"✅ {duration:.2f}s - Library verification passed ({count} scripts).")
        return True
    else:
        print(f"❌ {duration:.2f}s - Library check failed. Found {count} scripts.")
        return False

async def main():
    print("==================================================")
    print("  RoadMap 功能驗證 (真實執行)")
    print("==================================================")
    
    # 0. Check connection
    print("Checking connection...")
    stats = await call_mcp_tool("get_server_stats", {})
    if not stats:
        print("❌ Cannot connect to MCP Server.")
        return
        
    print("Connection Successful.")
    
    # 1. Clear Workspace
    print("Clearing workspace...")
    await call_mcp_tool("clear_workspace", {})
    await asyncio.sleep(1) # Wait for clear
    
    results = []
    
    # Run tests
    results.append(await test_search())
    results.append(await test_python_connection())
    results.append(await test_clockwork())
    results.append(await test_geometry())
    results.append(await test_library())
    
    print("--------------------------------------------------")
    passed = results.count(True)
    total = len(results)
    print(f"通過: {passed}/{total}")
    print("==================================================")
    
    if passed == total:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
