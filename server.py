from mcp.server.fastmcp import FastMCP
import time
import os
import json
import urllib.request
import urllib.error
import glob
from pathlib import Path

GUIDELINE_PATH = os.path.join(os.path.dirname(__file__), "MCP_GUIDELINES.md")
QUICK_REF_PATH = os.path.join(os.path.dirname(__file__), "QUICK_REFERENCE.md")

def _load_guidelines() -> tuple[str, str]:
    """Load content of guidelines and quick reference."""
    g_content = ""
    q_content = ""
    try:
        if os.path.exists(GUIDELINE_PATH):
            with open(GUIDELINE_PATH, "r", encoding="utf-8") as f:
                g_content = f.read()
        if os.path.exists(QUICK_REF_PATH):
            with open(QUICK_REF_PATH, "r", encoding="utf-8") as f:
                q_content = f.read()
    except Exception as e:
        print(f"⚠️ Warning: Failed to load guidelines: {e}")
    return g_content, q_content

# 初始化 Server
mcp = FastMCP("BIM_Assistant")

# ==========================================
# 工具列表
# ==========================================

import json
import urllib.request
import urllib.error
import subprocess
import datetime

# Global cache for process IDs
_cached_pids = []
_last_process_check_time = 0
_PROCESS_CACHE_TTL = 60  # Cache duration in seconds
_last_session_id = None # Track Dynamo Session ID

# Global state tracking for restart detection
_last_known_state = {
    "nodeCount": 0,
    "hasStartNode": False,
    "timestamp": 0
}

def _get_system_dynamo_processes(force_refresh: bool = False) -> list[int]:
    """
    Get list of PIDs for DynamoSandbox.exe and Revit.exe
    Uses caching to avoid calling 'tasklist' too frequently.
    """
    global _cached_pids, _last_process_check_time
    
    current_time = time.time()
    
    # Return cached if within TTL and not forced
    if not force_refresh and (current_time - _last_process_check_time < _PROCESS_CACHE_TTL):
        return _cached_pids

    pids = []
    try:
        # Check for DynamoSandbox.exe and Revit.exe
        # Using specific filters can be faster than listing all
        output = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq DynamoSandbox.exe" /FO CSV /NH', 
            shell=True
        ).decode('utf-8', errors='ignore')
        
        output_revit = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq Revit.exe" /FO CSV /NH', 
            shell=True
        ).decode('utf-8', errors='ignore')
        
        combined_output = output + "\n" + output_revit
        
        for line in combined_output.splitlines():
            if not line.strip(): continue
            parts = line.split(',')
            if len(parts) < 2: continue
            
            # Remove quotes
            image_name = parts[0].strip('"')
            pid_str = parts[1].strip('"')
            
            # Double check name (though filter handles it, good for safety)
            if image_name.lower() in ["dynamosandbox.exe", "revit.exe"]:
                if pid_str.isdigit():
                    pids.append(int(pid_str))
        
        # Update cache
        _cached_pids = pids
        _last_process_check_time = current_time
        
    except subprocess.CalledProcessError as e:
        import sys
        print(f"⚠️ [進程查詢失敗] tasklist 執行錯誤: {e}", file=sys.stderr)
        print(f"   Return Code: {e.returncode}, Output: {e.output}", file=sys.stderr)
        # Return cached data if available, otherwise empty
        return _cached_pids if _cached_pids else []
    except UnicodeDecodeError as e:
        import sys
        print(f"⚠️ [編碼錯誤] tasklist 輸出解碼失敗: {e}", file=sys.stderr)
        return _cached_pids if _cached_pids else []
    except Exception as e:
        import sys, traceback
        print(f"⚠️ [未預期錯誤] 進程查詢失敗: {e}", file=sys.stderr)
        print(f"   詳細資訊:\n{traceback.format_exc()}", file=sys.stderr)
        return _cached_pids if _cached_pids else []
        
    return pids

def _detect_potential_restart(data: dict) -> tuple[bool, str]:
    """
    偵測可能的 Dynamo 程式重啟
    使用啟發式方法：節點數劇減 + StartMCPServer 消失
    
    Args:
        data: 從 get_graph_status 回傳的資料
        
    Returns:
        (is_restart, reason): 是否可能重啟，以及原因說明
    """
    global _last_known_state
    
    current_count = data.get("nodeCount", 0)
    current_has_start = any(n.get("name") == "MCPControls.StartMCPServer" 
                           for n in data.get("nodes", []))
    
    # 初始化（第一次調用）
    if _last_known_state["timestamp"] == 0:
        _last_known_state.update({
            "nodeCount": current_count,
            "hasStartNode": current_has_start,
            "timestamp": time.time()
        })
        return False, ""
    
    restart_detected = False
    reasons = []
    
    # 檢查 1：節點數劇減（>= 3 降至 <= 2，且沒有 StartMCPServer）
    if _last_known_state["nodeCount"] >= 3 and current_count <= 2:
        # 進一步檢查：如果只剩 StartMCPServer，更可能是重啟
        if not current_has_start or current_count <= 1:
            restart_detected = True
            reasons.append(f"節點數從 {_last_known_state['nodeCount']} 劇減至 {current_count}")
    
    # 檢查 2：StartMCPServer 節點消失（且之前存在）
    if _last_known_state["hasStartNode"] and not current_has_start and current_count > 0:
        restart_detected = True
        reasons.append("StartMCPServer 節點消失")
    
    # 檢查 3：節點數歸零但之前大於 1
    if _last_known_state["nodeCount"] > 1 and current_count == 0:
        restart_detected = True
        reasons.append("工作區已清空")
    
    # 更新狀態
    _last_known_state.update({
        "nodeCount": current_count,
        "hasStartNode": current_has_start,
        "timestamp": time.time()
    })
    
    if restart_detected:
        return True, "; ".join(reasons)
    
    return False, ""

def _check_dynamo_connection() -> tuple[bool, str]:
    """
    Helper to verify if Dynamo listener is reachable.
    Also checks for Zombie processes if PID is available.
    """
    # 從配置檔讀取超時參數，提供預設值確保向後相容
    timeout_seconds = CONFIG.get("connection", {}).get("timeout_seconds", 5)
    
    server_conf = CONFIG.get("server", {})
    host = server_conf.get("host", "127.0.0.1")
    port = server_conf.get("port", 5050)
    
    url = f"http://{host}:{port}/mcp/"
    payload = json.dumps({"action": "get_graph_status"})
    
    try:
        req = urllib.request.Request(
            url, data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'}, method='POST'
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # 0. Check for Session Change (New Feature)
            global _last_session_id
            current_session_id = data.get("sessionId")
            
            if current_session_id:
                if _last_session_id is not None and current_session_id != _last_session_id:
                    print(f"🔄 [SESSION CHANGED] Detected new Dynamo session: {_last_session_id} -> {current_session_id}")
                    # Optional: We could invalidate caches here if needed
                    # _commonNodesCache = None 
                
                if _last_session_id != current_session_id:
                     _last_session_id = current_session_id
            
            # 1. Check for PID (New Feature)
            if "processId" in data:
                connected_pid = int(data["processId"])
                # Request fresh PIDs only if we suspect a mismatch, but for general check use cache first?
                # Actually, if we are verifying connection, we might want to be sure. 
                # But to save time, let's use cache first. If not found, THEN force refresh.
                system_pids = _get_system_dynamo_processes(force_refresh=False)
                
                if connected_pid not in system_pids:
                     # Try one more time with force refresh
                     system_pids = _get_system_dynamo_processes(force_refresh=True)
                
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
            
            # 3. Check for potential Dynamo restart
            restart_detected, restart_reason = _detect_potential_restart(data)
            if restart_detected:
                warning_msg = f"🔄 **偵測到可能的 Dynamo 重啟**: {restart_reason}\n\n建議您重新放置 'MCPControls.StartMCPServer' 節點以確保連線穩定。"
                data["mcp_restart_warning"] = warning_msg
                print(f"🔄 [POTENTIAL RESTART] {restart_reason}")

            return True, json.dumps(data) 
            
    except urllib.error.HTTPError as e:
        return False, f"HTTP 錯誤 {e.code}: {e.reason} - Dynamo 伺服器回應異常"
    except urllib.error.URLError as e:
        if "timed out" in str(e.reason).lower():
            return False, f"連線逾時 ({timeout_seconds}秒) - Dynamo 可能未啟動或伺服器未回應"
        return False, f"連線失敗: {e.reason} - 請確認 Dynamo 是否正在執行"
    except json.JSONDecodeError as e:
        return False, f"JSON 解析錯誤: {e} - 伺服器回應格式異常"
    except Exception as e:
        import traceback
        error_detail = f"未預期錯誤: {e}\n詳細資訊:\n{traceback.format_exc()}"
        print(f"⚠️ [連線檢查失敗] {error_detail}", file=sys.stderr)
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
    # 強制檢查連線
    is_ok, status_or_err = _check_dynamo_connection()
    
    server_conf = CONFIG.get("server", {})
    host = server_conf.get("host", "127.0.0.1")
    port = server_conf.get("port", 5050)
    
    if not is_ok:
        return f"❌ 失敗: 無法連線至 Dynamo ({host}:{port})。請確認：1. Dynamo 已開啟 2. 確定有載入 DynamoMCPListener 插件。 (錯誤: {status_or_err})"

    url = f"http://{host}:{port}/mcp/"
    
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

    server_conf = CONFIG.get("server", {})
    host = server_conf.get("host", "127.0.0.1")
    port = server_conf.get("port", 5050)
    url = f"http://{host}:{port}/mcp/"
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

    server_conf = CONFIG.get("server", {})
    host = server_conf.get("host", "127.0.0.1")
    port = server_conf.get("port", 5050)
    url = f"http://{host}:{port}/mcp/"
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
# 新增工具: 規範查詢 (Guideline Enforcement)
# ==========================================
@mcp.tool()
def get_mcp_guidelines() -> str:
    """
    Get the full content of MCP_GUIDELINES.md and QUICK_REFERENCE.md.
    AI Agents should consult this when encountering errors or at the start of a session.
    
    Returns:
        Combined string of both files.
    """
    g_content, q_content = _load_guidelines()
    return f"# MCP GUIDELINES\n\n{g_content}\n\n# QUICK REFERENCE\n\n{q_content}"

@mcp.prompt()
def mcp_rules() -> str:
    """
    System prompt containing the core rules for interacting with Dynamo MCP.
    """
    g_content, q_content = _load_guidelines()
    return f"""You are an intelligent BIM Assistant controlling Autodesk Dynamo via MCP.
    
CRITICAL OPERATIONAL RULES:
{q_content}

DETAILED GUIDELINES:
{g_content}
"""

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
    print("==========================================")
    print("   BIM Assistant MCP Server (v2.3)   ")
    print("==========================================")
    print(f"Server Path: {os.path.abspath(__file__)}")
    print(f"Config Path: {CONFIG_PATH}")
    if CONFIG:
        print("✅ Configuration loaded successfully.")
    else:
        print("⚠️  Warning: Configuration NOT loaded or empty.")
    
    print(f"Script Library: {SCRIPT_DIR}")
    if not os.path.exists(SCRIPT_DIR):
        print(f"Creating script directory: {SCRIPT_DIR}")
        os.makedirs(SCRIPT_DIR)
    
    print("Starting FastMCP Server...")
    print("==========================================")
    
    # CRITICAL STARTUP WARNINGS
    print("\n" + "!" * 50)
    print("CRITICAL WARNING: PLEASE READ")
    print("!" * 50)
    print("1. 若需重啟 Dynamo，請務必先按 Ctrl+C 停止此 Server！")
    print("   (Stop this server BEFORE closing Dynamo window)")
    print("2. 每次對話開始前，建議使用 'get_mcp_guidelines' 複習規範。")
    print("!" * 50 + "\n")
    
    mcp.run(transport="sse")
