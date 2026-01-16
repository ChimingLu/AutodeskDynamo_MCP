# Copyright 2026 ChimingLu.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mcp.server.fastmcp import FastMCP
import time
import os
import json
import urllib.request
import urllib.error
import glob
from pathlib import Path

GUIDELINE_PATH = os.path.join(os.path.dirname(__file__), "GEMINI.md")
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
        print(f"[WARN] Warning: Failed to load guidelines: {e}")
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

# ==========================================
#  節點元數據快取與路由邏輯
# ==========================================

# 節點元數據快取（從 common_nodes.json 載入）
_common_nodes_metadata = None

def _load_common_nodes_metadata() -> dict:
    """
    從 DynamoViewExtension/common_nodes.json 載入節點元數據
    包含 Overload 定義與創建策略
    """
    global _common_nodes_metadata
    
    if _common_nodes_metadata is not None:
        return _common_nodes_metadata
    
    try:
        metadata_path = os.path.join(
            os.path.dirname(__file__),
            "DynamoViewExtension",
            "common_nodes.json"
        )
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            nodes_list = json.load(f)
        
        # 轉換為字典格式，以 name 為 key 方便查詢
        _common_nodes_metadata = {}
        for node in nodes_list:
            _common_nodes_metadata[node["name"]] = node
        
        print(f"[OK] Loaded {len(_common_nodes_metadata)} nodes metadata")
        return _common_nodes_metadata
        
    except Exception as e:
        print(f"[WARN] Failed to load node metadata: {e}")
        return {}

def infer_overload_from_params(node_name: str, params: dict) -> str:
    """
    根據參數自動推斷 Overload 版本
    
    Args:
        node_name: 節點名稱（如 "Point.ByCoordinates"）
        params: 參數字典（如 {"x": 0, "y": 0, "z": 100}）
    
    Returns:
        Overload ID（如 "3D"），若無法推斷則回傳 None
    """
    if node_name == "Point.ByCoordinates":
        return "3D" if "z" in params else "2D"
    elif node_name == "Vector.ByCoordinates":
        return "3D" if "z" in params else "2D"
    
    return None

def route_node_creation(node_spec: dict) -> dict:
    """
    智慧路由：根據節點類型選擇最佳創建策略
    """
    node_name = node_spec.get("name", "")
    metadata = _load_common_nodes_metadata()
    
    # 從元數據查詢節點資訊
    node_info = metadata.get(node_name, {})
    strategy = node_info.get("creationStrategy", "NATIVE_DIRECT")
    
    # 如果是 NATIVE_WITH_OVERLOAD 策略
    if strategy == "NATIVE_WITH_OVERLOAD":
        # 使用明確指定的 Overload，或自動推斷
        if "overload" not in node_spec:
            params = node_spec.get("params", {})
            inferred = infer_overload_from_params(node_name, params)
            if inferred:
                node_spec["overload"] = inferred
                print(f"[INFO] Auto-inferred Overload for {node_name}: {inferred}")
    
    # 標記策略
    node_spec["_strategy"] = strategy
    return node_spec

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
        print(f"[WARN] [Process Check Failed] tasklist error: {e}", file=sys.stderr)
        print(f"   Return Code: {e.returncode}, Output: {e.output}", file=sys.stderr)
        # Return cached data if available, otherwise empty
        return _cached_pids if _cached_pids else []
    except UnicodeDecodeError as e:
        import sys
        print(f"[WARN] [Encoding Error] tasklist output decode failed: {e}", file=sys.stderr)
        return _cached_pids if _cached_pids else []
    except Exception as e:
        import sys, traceback
        print(f"[WARN] [Unexpected Error] Process check failed: {e}", file=sys.stderr)
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
                    print(f"[SESSION CHANGED] Detected new Dynamo session: {_last_session_id} -> {current_session_id}")
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
                    return False, f"[WARN] Anomaly: Connected to PID {connected_pid}, but process seems dead or undetected."
                
                # Case B: Multiple potential instances
                # Case C: Connected PID is there, but there are others (Potential Zombie scenario)
                if len(system_pids) > 1:
                     # Identify if we are connected to one of them.
                     other_pids = [p for p in system_pids if p != connected_pid]
                     if other_pids:
                         return False, f"[WARN] **CRITICAL**: Multiple Dynamo/Revit processes detected (PIDs: {system_pids}).\nCurrently connected to PID: {connected_pid}.\nThis usually indicates Zombie Processes.\nPlease FORCE KILL all Revit/Dynamo processes and retry."

            # 2. Check for StartMCPServer Node (New Feature)
            # User wants to be warned if the node is missing, even if connection works (via auto-start)
            has_start_node = False
            if "nodes" in data and isinstance(data["nodes"], list):
                for node in data["nodes"]:
                    if node.get("name") == "MCPControls.StartMCPServer":
                        has_start_node = True
                        break
            
            if not has_start_node:
                data["mcp_warning"] = "[Suggestion] 'StartMCPServer' node not detected. It is recommended to place it for stability."
            
            # 3. Check for potential Dynamo restart
            restart_detected, restart_reason = _detect_potential_restart(data)
            if restart_detected:
                warning_msg = f"[RESTART DETECTED] Possible Dynamo restart: {restart_reason}\n\nRecommended: Re-place 'MCPControls.StartMCPServer' node."
                data["mcp_restart_warning"] = warning_msg
                print(f"[POTENTIAL RESTART] {restart_reason}")

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
        print(f"[WARN] [Connection Check Failed] {error_detail}", file=sys.stderr)
        return False, str(e)

# ==========================================
# 新增工具: Dynamo 自動化操作
# ==========================================
@mcp.tool()
def execute_dynamo_instructions(instructions: str, clear_before_execute: bool = False, base_x: float = 0, base_y: float = 0) -> str:
    """
    在 Dynamo 中執行一組指令，創建節點與連線。
    
    參數:
        instructions: 描述節點與連線的 JSON 字串。
        clear_before_execute: 若為 True，會在放置新節點前清空當前工作區。
        base_x: 可選的 X 軸偏移量，將應用於所有節點。
        base_y: 可選的 Y 軸偏移量，將應用於所有節點。
                      範例:
                      {
                        "nodes": [
                          {"id": "n1", "name": "Point.ByCoordinates", "x": 0, "y": 0}
                        ],
                        "connectors": []
                      }
                      
    返回:
        執行狀態訊息。
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

        # 1. 智慧節點路由與自動擴展
        expanded_nodes = []
        expanded_connectors = json_data.get("connectors", [])
        
        if "nodes" in json_data:
            metadata = _load_common_nodes_metadata()
            for node in json_data["nodes"]:
                # 先進行路由處理
                route_node_creation(node)
                expanded_nodes.append(node)
                
                # 如果是原生節點且有 params，則進行「自動擴展」
                strategy = node.get("_strategy", "")
                params = node.get("params", {})
                node_id = node.get("id")
                
                if (strategy in ["NATIVE_DIRECT", "NATIVE_WITH_OVERLOAD"]) and params and node_id:
                    node_name = node.get("name")
                    node_info = metadata.get(node_name, {})
                    
                    # 取得正確的埠位順序
                    input_ports = node_info.get("inputs", [])
                    overload_id = node.get("overload")
                    if overload_id and "overloads" in node_info:
                        for ov in node_info["overloads"]:
                            if ov["id"] == overload_id:
                                input_ports = ov.get("inputs", input_ports)
                                break
                    
                    # 為每個參數建立 Number 節點
                    for i, port_name in enumerate(input_ports):
                        if port_name in params:
                            val = params[port_name]
                            param_node_id = f"{node_id}_{port_name}_{int(time.time()*1000) % 10000}"
                            
                            # 建立輸入節點
                            param_node = {
                                "id": param_node_id,
                                "name": "Number",
                                "value": str(val),
                                "x": node.get("x", 0) - 200, # 放在主節點左側
                                "y": node.get("y", 0) + (i * 80),
                                "_strategy": "CODE_BLOCK",
                                "preview": node.get("preview", True)  # 繼承父節點的預覽設定
                            }
                            expanded_nodes.append(param_node)
                            
                            # 建立連線
                            expanded_connectors.append({
                                "from": param_node_id,
                                "to": node_id,
                                "fromPort": 0,
                                "toPort": i
                            })
            
            json_data["nodes"] = expanded_nodes
            json_data["connectors"] = expanded_connectors

        # 2. Apply offsets (已擴展後的節點)
        if "nodes" in json_data:
            for node in json_data["nodes"]:
                if "x" in node:
                    node["x"] = float(node.get("x", 0)) + base_x
                if "y" in node:
                    node["y"] = float(node.get("y", 0)) + base_y
        
        # 3. 序列化
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
    列出當前 Dynamo 工作階段中的可用節點，包含來自套件的 .dyf 自訂節點。
    
    參數:
        filter_text: 可選的篩選文字，用於過濾節點名稱。
        search_scope: "default" (建議) 搜尋常用節點 + 全域清單中的匹配項 (限制 20 筆)。
                      "all" 搜尋整個全域節點庫 (限制 200 筆)。
                      僅在使用者明確要求「搜尋所有節點」或「全域搜尋」時使用 "all"。
        detail: 返回的詳細程度:
                "basic" (預設) - 僅包含名稱與完整名稱 (最快，最少 token)
                "standard" - 新增輸入、輸出與類別 (包含 .dyf 元數據)
                "full" - 包含描述 (最多 token)
        
    返回:
        包含節點元數據的 JSON 字串。
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
    取得 Dynamo 工作區中所有節點的當前狀態，包含錯誤與警告訊息。
    
    返回:
        包含工作區名稱、節點數量與個別節點狀態的 JSON 字串。
    """
    # 直接回傳檢查結果
    is_ok, status_or_err = _check_dynamo_connection()
    return status_or_err if is_ok else f"❌ 失敗: Dynamo 監聽器未啟動。 ({status_or_err})"


@mcp.tool()
def clear_workspace() -> str:
    """
    清除 Dynamo 工作區中的所有節點與連線。
    建議在開始新設計或節點重疊時使用此功能。
    
    返回:
        執行狀態訊息。
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
    取得 GEMINI.md 與 QUICK_REFERENCE.md 的完整內容。
    AI 代理應在遭遇錯誤或工作階段開始時查閱此文件。
    
    返回:
        合併兩個檔案內容的字串。
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
    取得腳本庫中的可用腳本清單。
    
    腳本儲存位置: <專案根目錄>/DynamoScripts/
    此目錄中的所有 .json 檔案會被自動探索。
    
    返回:
        包含腳本元數據 (名稱、描述、檔案路徑) 的 JSON 字串清單。
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
    將 Dynamo 腳本儲存至腳本庫，供未來重複使用。
    
    檔案儲存位置: <專案根目錄>/DynamoScripts/<名稱>.json
    此資料夾是可重複使用的 Dynamo 圖表定義的中央儲存庫。
    
    參數:
        name: 腳本的唯一名稱 (例如: 'grid_2x2')。
        description: 腳本功能的簡短描述。
        content_json: 節點與連線的 JSON 指令。
        
    返回:
        包含絕對檔案路徑的成功訊息，或錯誤訊息。
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
    從腳本庫載入 Dynamo 腳本內容。
    
    載入來源: <專案根目錄>/DynamoScripts/<名稱>.json
    返回的 JSON 可直接傳遞給 execute_dynamo_instructions 執行。
    
    參數:
        name: 要載入的腳本名稱 (不含 .json 副檔名)。
        base_x: 可選的 X 軸偏移量，將應用於腳本中的所有節點。
        base_y: 可選的 Y 軸偏移量，將應用於腳本中的所有節點。
        
    返回:
        可直接執行的 JSON 內容字串 (節點與連線)。
        若腳本未找到則返回錯誤訊息。
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
    import sys
    
    # helper for stderr logging
    def log_startup(msg):
        print(msg, file=sys.stderr)

    log_startup("==========================================")
    log_startup("   BIM Assistant MCP Server (v2.3)   ")
    log_startup("==========================================")
    log_startup(f"Server Path: {os.path.abspath(__file__)}")
    log_startup(f"Config Path: {CONFIG_PATH}")
    if CONFIG:
        log_startup("[OK] Configuration loaded successfully.")
    else:
        log_startup("[WARN] Warning: Configuration NOT loaded or empty.")
    
    log_startup(f"Script Library: {SCRIPT_DIR}")
    if not os.path.exists(SCRIPT_DIR):
        log_startup(f"Creating script directory: {SCRIPT_DIR}")
        os.makedirs(SCRIPT_DIR)
    
    log_startup("Starting FastMCP Server...")
    log_startup("==========================================")
    
    # CRITICAL STARTUP WARNINGS
    log_startup("\n" + "!" * 50)
    log_startup("CRITICAL WARNING: PLEASE READ")
    log_startup("!" * 50)
    log_startup("1. If you need to restart Dynamo, please press Ctrl+C to stop this Server first!")
    log_startup("   (Stop this server BEFORE closing Dynamo window)")
    log_startup("2. Before starting each conversation, it is recommended to use 'get_mcp_guidelines' to review the specifications.")
    log_startup("!" * 50 + "\n")
    
    # Use stdio transport for Claude Desktop integration
    mcp.run(transport="stdio")
