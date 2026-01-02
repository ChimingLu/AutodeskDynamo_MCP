from mcp.server.fastmcp import FastMCP
import time
import os
import json
import urllib.request
import urllib.error
import glob

# 初始化 Server
mcp = FastMCP("BIM_Assistant")

# ==========================================
# 既有工具 (保留)
# ==========================================
@mcp.tool()
def add(a: int, b: int) -> int:
    """Basic addition."""
    return a + b

@mcp.tool()
def get_material_specs(material_name: str) -> dict:
    """Mock database search for materials."""
    db = {"Concrete": 2400, "Steel": 7850}
    val = db.get(material_name, 0)
    return {"density": val, "unit": "kg/m3"}

# ==========================================
# 新增工具: AI 顧問
# ==========================================
@mcp.tool()
def ask_ai_consultant(question: str, context: str = "") -> str:
    """
    Ask the AI Consultant a question about BIM, Revit API, or Dynamo strategies.
    
    Args:
        question: The user's question (e.g., "How do I filter walls by height?").
        context: Optional background info (e.g., list of current node names).
        
    Returns:
        A text advice string.
    """
    # 模擬思考時間，增加真實感
    time.sleep(1)
    
    q_lower = question.lower()
    
    # 這裡未來可以替換成 OpenAI / Gemini API call
    # response = openai.ChatCompletion.create(...)
    
    # 目前的模擬邏輯 (Mock Logic)
    if "filter" in q_lower and "wall" in q_lower:
        return (
            "💡 **AI 建議**: 若要篩選牆，建議使用 `Element.GetParameterValueByName` "
            "讀取 'Unconnected Height'，然後搭配 `List.FilterByBoolMask`。\n"
            "若要過濾類型，請使用 `Element.Name` 節點。"
        )
    
    elif "warning" in q_lower or "error" in q_lower:
        return (
            "⚠️ **Debug 建議**: 遇到黃色警告通常是資料結構問題 (List Level)。"
            "請檢查您的輸入是否需要 `List.Flatten`，或者改變節點的 L2/L3 設定。"
        )
        
    elif "python" in q_lower:
        return (
            "🐍 **Python 提示**: 在 Dynamo Python Node 中，請記得 `UnwrapElement(IN[0])` "
            "才能呼叫 Revit API 的原生方法。"
        )
        
    elif "api" in q_lower:
        return (
            "📘 **API 知識**: Revit API 中，修改模型必須在 `Transaction` 內進行。"
            "雖然 Dynamo 節點通常自動處理，但在 Python Script 中要特別注意 TransactionManager。"
        )

    # 預設回應
    return (
        f"🤖 **AI 收到問題**: '{question}'\n"
        f"目前我尚未連接真實的 LLM (如 GPT-4)，但您可以問我關於 'filter walls', 'python script', 或 'api' 的問題來測試我的關鍵字觸發功能。"
    )

import json
import urllib.request
import urllib.error
import subprocess

def _get_system_dynamo_processes() -> list[int]:
    """Get list of PIDs for DynamoSandbox.exe and Revit.exe"""
    pids = []
    try:
        # Check for DynamoSandbox.exe and Revit.exe
        cmd = 'tasklist /FI "IMAGENAME eq DynamoSandbox.exe" /FI "IMAGENAME eq Revit.exe" /FO CSV /NH'
        # Note: tasklist filters are AND by default for different properties, but same property?
        # Actually tasklist filters are additive if you simply run it? No, usually checking multiple images needs separate commands or logic.
        # "IMAGENAME eq A" OR "IMAGENAME eq B" is not directly supported in one filter flag usually without /OR which doesn't exist.
        # Let's run twice or just grep name.
        # Simpler: List all locally and filter in python to be safe.
        
        output = subprocess.check_output("tasklist /FO CSV /NH", shell=True).decode('utf-8', errors='ignore')
        for line in output.splitlines():
            if not line.strip(): continue
            parts = line.split(',')
            if len(parts) < 2: continue
            
            # Remove quotes
            image_name = parts[0].strip('"')
            pid_str = parts[1].strip('"')
            
            if image_name.lower() in ["dynamosandbox.exe", "revit.exe"]:
                if pid_str.isdigit():
                    pids.append(int(pid_str))
    except Exception:
        pass
    return pids

def _check_dynamo_connection() -> tuple[bool, str]:
    """
    Helper to verify if Dynamo listener is reachable.
    Also checks for Zombie processes if PID is available.
    """
    url = "http://127.0.0.1:5050/mcp/"
    payload = json.dumps({"action": "get_graph_status"})
    try:
        req = urllib.request.Request(
            url, data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST'
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # 1. Check for PID (New Feature)
            if "processId" in data:
                connected_pid = int(data["processId"])
                system_pids = _get_system_dynamo_processes()
                
                # Case A: Connected PID not found active
                # (Note: tasklist might miss it if it closed very fast, but usually valid for zombies)
                if connected_pid not in system_pids:
                    # Case A: Connected PID not found active (Zombie or Phantom)
                    return False, f"⚠️ 異常: 連線至 PID {connected_pid}，但該程序似乎已不存在或無法被 tasklist 偵測。請確認 Dynamo 是否正常執行。"
                
                # Case B: Multiple potential instances
                # Case C: Connected PID is there, but there are others (Potential Zombie scenario)
                if len(system_pids) > 1:
                     # Identify if we are connected to one of them.
                     other_pids = [p for p in system_pids if p != connected_pid]
                     if other_pids:
                         return False, f"⚠️ **嚴重警告**: 偵測到多個 Dynamo/Revit 程序 (PIDs: {system_pids})。\n目前連線至 PID: {connected_pid}。\n這通常表示舊的 Dynamo 未完全關閉 (Zombie Process)。\n請務必**強制結束**所有 Revit/Dynamo 程序後再重試，否則指令將無法正確送達。"

            # 2. Check for StartMCPServer Node (New Feature)
            # User wants to be warned if the node is missing, even if connection works (via auto-start)
            has_start_node = False
            if "nodes" in data and isinstance(data["nodes"], list):
                for node in data["nodes"]:
                    if node.get("name") == "MCPControls.StartMCPServer":
                        has_start_node = True
                        break
            
            if not has_start_node:
                data["mcp_warning"] = "⚠️ 建議: 未偵測到 'StartMCPServer' 節點。雖然連線正常，但建議放置該節點以確保穩定性與視覺確認。"
                return True, json.dumps(data)

            return True, json.dumps(data) 
            
    except Exception as e:
        return False, str(e)

# ==========================================
# 新增工具: Dynamo 自動化操作
# ==========================================
@mcp.tool()
def execute_dynamo_instructions(instructions: str, clear_before_execute: bool = False, base_x: float = 0, base_y: float = 0) -> str:
    """
    Execute a set of instructions to create nodes and connections in Dynamo.
    
    Args:
        instructions: A JSON string describing the nodes and connections.
        clear_before_execute: If True, clears the current workspace before placing new nodes.
        base_x: Optional X offset to add to all nodes.
        base_y: Optional Y offset to add to all nodes.
                      Example:
                      {
                        "nodes": [
                          {"id": "n1", "name": "Point.ByCoordinates", "x": 0, "y": 0}
                        ],
                        "connectors": []
                      }
                      
    Returns:
        Status message.
    """
    # 強制檢查連線
    is_ok, status_or_err = _check_dynamo_connection()
    if not is_ok:
        return f"❌ 失敗: 無法連線至 Dynamo (localhost:5050)。請確認：1. Dynamo 已開啟 2. 確定有載入 DynamoMCPListener 插件。 (錯誤: {status_or_err})"

    url = "http://127.0.0.1:5050/mcp/"
    
    try:
        # Validate JSON
        try:
            json_data = json.loads(instructions)
        except json.JSONDecodeError:
            return "Error: Invalid JSON format."

        # Apply offsets
        if base_x != 0 or base_y != 0:
            if "nodes" in json_data:
                for node in json_data["nodes"]:
                    if "x" in node:
                        node["x"] = float(node["x"]) + base_x
                    if "y" in node:
                        node["y"] = float(node["y"]) + base_y
            instructions = json.dumps(json_data)

        # If requested, clear workspace first
        if clear_before_execute:
            try:
                clear_payload = json.dumps({"action": "clear_graph"})
                req_clear = urllib.request.Request(
                    url, data=clear_payload.encode('utf-8'),
                    headers={'Content-Type': 'application/json'}, method='POST'
                )
                with urllib.request.urlopen(req_clear) as resp:
                    resp.read()
            except urllib.error.URLError:
                return "❌ 失敗: 清除工作區時發生連線中斷。"

        req = urllib.request.Request(
            url, 
            data=instructions.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return f"✅ 成功發送指令至 Dynamo。回應: {response.read().decode('utf-8')}"
            
    except Exception as e:
        return f"發生錯誤: {str(e)}"

# ==========================================
# 新增工具: 列出可用節點
# ==========================================
@mcp.tool()
def list_available_nodes(filter_text: str = "", search_scope: str = "default", detail: str = "basic") -> str:
    """
    List available nodes in the current Dynamo session, including .dyf custom nodes from packages.
    
    Args:
        filter_text: Optional text to filter node names.
        search_scope: "default" (Recommended) searches Common Nodes + matches from Global list (limit 20).
                      "all" searches entire Global Node Library (limit 200). 
                      Use "all" ONLY if the user explicitly asks to "search all nodes" or "global search".
        detail: Level of detail to return:
                "basic" (default) - Only name and fullName (fastest, lowest tokens)
                "standard" - Adds inputs, outputs, and category (includes .dyf metadata)
                "full" - Includes description (highest tokens)
        
    Returns:
        JSON string of available nodes with metadata.
    """
    # 強制檢查連線
    is_ok, status_or_err = _check_dynamo_connection()
    if not is_ok:
        return f"❌ 失敗: 無法連線至 Dynamo。 (錯誤: {status_or_err})"

    url = "http://127.0.0.1:5050/mcp/"
    payload = json.dumps({
        "action": "list_nodes", 
        "filter": filter_text,
        "scope": search_scope,
        "detail": detail
    })
    
    try:
        req = urllib.request.Request(
            url, 
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
            
    except Exception as e:
        return f"Error listing nodes: {str(e)}"


@mcp.tool()
def analyze_workspace() -> str:
    """
    Get the current state of all nodes in the Dynamo workspace, including errors and warnings.
    
    Returns:
        JSON string containing workspace name, node count, and individual node states.
    """
    # 直接回傳檢查結果
    is_ok, status_or_err = _check_dynamo_connection()
    return status_or_err if is_ok else f"❌ 失敗: Dynamo 監聽器未啟動。 ({status_or_err})"


@mcp.tool()
def clear_workspace() -> str:
    """
    Clear all nodes and connectors from the current Dynamo workspace.
    Use this before starting a new design or when nodes are overlapping.
    
    Returns:
        Status message.
    """
    # 強制檢查連線
    is_ok, status_or_err = _check_dynamo_connection()
    if not is_ok:
        return f"❌ 失敗: 無法清空，連線已中斷。 ({status_or_err})"

    url = "http://127.0.0.1:5050/mcp/"
    payload = json.dumps({"action": "clear_graph"})
    
    try:
        req = urllib.request.Request(
            url, 
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
            
    except Exception as e:
        return f"Error clearing workspace: {str(e)}"



# ==========================================
# 新增工具: 腳本庫管理 (Script Library)
# ==========================================
# ==========================================
# 載入設定檔 (mcp_config.json)
# ==========================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "mcp_config.json")
CONFIG = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
    except:
        pass

# 根據設定檔定義腳本目錄
script_rel_path = CONFIG.get("paths", {}).get("scripts", "DynamoScripts")
SCRIPT_DIR = os.path.join(os.path.dirname(__file__), script_rel_path)

if not os.path.exists(SCRIPT_DIR):
    os.makedirs(SCRIPT_DIR)

@mcp.tool()
def get_script_library() -> str:
    """
    Get a list of available scripts in the library.
    
    Scripts are stored in: <PROJECT_ROOT>/DynamoScripts/
    All .json files in this directory are automatically discovered.
    
    Returns:
        JSON string list of script metadata (name, description, file path).
    """
    scripts = []
    try:
        files = glob.glob(os.path.join(SCRIPT_DIR, "*.json"))
        for f in files:
            name = os.path.basename(f).replace(".json", "")
            desc = "No description"
            try:
                with open(f, "r", encoding="utf-8") as rf:
                    data = json.load(rf)
                    desc = data.get("description", "No description")
            except:
                pass
            scripts.append({
                "name": name, 
                "description": desc,
                "path": f
            })
        return json.dumps(scripts, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error reading library: {str(e)}"

@mcp.tool()
def save_script_to_library(name: str, description: str, content_json: str) -> str:
    """
    Save a Dynamo script to the library for future reuse.
    
    Files are saved to: <PROJECT_ROOT>/DynamoScripts/<name>.json
    This folder is the central repository for reusable Dynamo graph definitions.
    
    Args:
        name: Unique name for the script (e.g., 'grid_2x2').
        description: Brief description of what the script does.
        content_json: The JSON instructions for nodes and connectors.
        
    Returns:
        Success message with absolute file path, or error message.
    """
    try:
        # Validate content JSON
        content = json.loads(content_json)
        
        file_path = os.path.join(SCRIPT_DIR, f"{name}.json")
        data = {
            "description": description,
            "content": content
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        abs_path = os.path.abspath(file_path)
        return f"Script '{name}' saved successfully to: {abs_path}"
    except Exception as e:
        return f"Error saving script: {str(e)}"

@mcp.tool()
def load_script_from_library(name: str, base_x: float = 0, base_y: float = 0) -> str:
    """
    Load a Dynamo script content from the library.
    
    Loads from: <PROJECT_ROOT>/DynamoScripts/<name>.json
    The returned JSON can be directly passed to execute_dynamo_instructions.
    
    Args:
        name: The name of the script to load (without .json extension).
        base_x: Optional X offset to add to all nodes in the script.
        base_y: Optional Y offset to add to all nodes in the script.
        
    Returns:
        The content JSON string (nodes and connectors) ready for execution.
        Returns error message if script not found.
    """
    try:
        file_path = os.path.join(SCRIPT_DIR, f"{name}.json")
        if not os.path.exists(file_path):
            return f"Error: Script '{name}' not found."
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            content = data.get("content", {})
            
            # Apply offsets
            if base_x != 0 or base_y != 0:
                if "nodes" in content:
                    for node in content["nodes"]:
                        if "x" in node:
                            node["x"] = float(node["x"]) + base_x
                        if "y" in node:
                            node["y"] = float(node["y"]) + base_y
            
            return json.dumps(content)
    except Exception as e:
        return f"Error loading script: {str(e)}"

if __name__ == "__main__":
    print("Starting BIM Assistant MCP Server (Version 2.2)...")
    mcp.run(transport="sse")
