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

"""
Dynamo MCP WebSocket Manager
簡化版 - 只處理 WebSocket 連線（Dynamo 和 Node.js MCP Bridge）
"""

import time, os, json, glob, asyncio, websockets, threading, uuid, subprocess, sys
from typing import Any, Dict, Optional, List

# 全域日誌函數
def log(m): print(m, file=sys.stderr)

# ==========================================
# 基礎路徑與設定
# ==========================================
GUIDELINE_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "GEMINI.md"))
QUICK_REF_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "QUICK_REFERENCE.md"))
CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp_config.json"))

CONFIG = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            CONFIG = json.load(f)
    except Exception as e:
        log(f"Failed to load config: {e}")

script_rel_path = CONFIG.get("paths", {}).get("scripts", "DynamoScripts")
SCRIPT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", script_rel_path))
if not os.path.exists(SCRIPT_DIR):
    os.makedirs(SCRIPT_DIR)

# ==========================================
# 工具邏輯與輔助函式
# ==========================================

_common_nodes_metadata = None

def _load_guidelines() -> tuple[str, str]:
    g_content, q_content = "", ""
    try:
        if os.path.exists(GUIDELINE_PATH):
            with open(GUIDELINE_PATH, "r", encoding="utf-8") as f:
                g_content = f.read()
        if os.path.exists(QUICK_REF_PATH):
            with open(QUICK_REF_PATH, "r", encoding="utf-8") as f:
                q_content = f.read()
    except Exception as e:
        log(f"[WARN] Failed to load guidelines: {e}")
    return g_content, q_content

def _load_common_nodes_metadata() -> dict:
    global _common_nodes_metadata
    if _common_nodes_metadata is not None: return _common_nodes_metadata
    try:
        metadata_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "DynamoViewExtension", "common_nodes.json"))
        with open(metadata_path, "r", encoding="utf-8") as f:
            nodes_list = json.load(f)
        _common_nodes_metadata = {node["name"]: node for node in nodes_list}
        return _common_nodes_metadata
    except Exception as e:
        log(f"[WARN] Failed to load node metadata: {e}")
        return {}

def route_node_creation(node_spec: dict) -> dict:
    node_name = node_spec.get("name", "")
    metadata = _load_common_nodes_metadata()
    node_info = metadata.get(node_name, {})
    strategy = node_info.get("creationStrategy", "NATIVE_DIRECT")
    node_spec["_strategy"] = strategy
    return node_spec

# ==========================================
# WebSocket Manager for Dynamo
# ==========================================

class WebSocketManager:
    def __init__(self):
        self.active_sessions = {}  # {session_id: websocket}
        self.session_info = {}     # {session_id: {fileName, connectedAt, lastSeen, stats: {cmds, errors}}}
        self.queues = {}           # {session_id: asyncio.Queue}
        self._lock = threading.Lock()
        self.start_time = time.time()

    async def register(self, websocket, session_id, file_name):
        now = time.time()
        with self._lock:
            # 如果 session_id 已存在，先關閉舊的 (如果還在)
            if session_id in self.active_sessions:
                log(f"[Dynamo-WS] Refreshing existing session: {session_id}")
            
            self.active_sessions[session_id] = websocket
            self.session_info[session_id] = {
                "fileName": file_name, 
                "connectedAt": now,
                "lastSeen": now,
                "stats": {"cmds": 0, "errors": 0}
            }
            self.queues[session_id] = asyncio.Queue()
        log(f"[Dynamo-WS] New connection: {session_id} ({file_name})")

    async def unregister(self, session_id):
        with self._lock:
            self.active_sessions.pop(session_id, None)
            self.session_info.pop(session_id, None)
            self.queues.pop(session_id, None)
        log(f"[Dynamo-WS] Connection closed: {session_id}")

    async def _handle_connection(self, websocket):
        session_id = str(uuid.uuid4())
        try:
            # 增加通訊超時，避免掛死
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            if data.get("action") == "handshake":
                file_name = data.get("fileName", "Unknown")
                session_id = data.get("sessionId", session_id)
                await self.register(websocket, session_id, file_name)
                await websocket.send(json.dumps({"status": "connected", "sessionId": session_id}))
                
                async for msg in websocket:
                    try:
                        event = json.loads(msg)
                        with self._lock:
                            if session_id in self.session_info:
                                self.session_info[session_id]["lastSeen"] = time.time()
                        
                        if event.get("action") == "status_update":
                            pass  # 可在此處理即時狀態
                        else:
                            if session_id in self.queues:
                                await self.queues[session_id].put(event)
                    except Exception as e:
                        log(f"[Dynamo-WS] Msg Error: {e}")
        except asyncio.TimeoutError:
            log(f"[Dynamo-WS] Handshake timeout")
        except websockets.exceptions.ConnectionClosed: 
            pass
        finally: 
            await self.unregister(session_id)

    async def run(self):
        async with websockets.serve(self._handle_connection, self.host, self.port):
            await asyncio.Future()

    def start_server(self, host, port):
        self.host = host
        self.port = port
        threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True).start()
        log(f"[Dynamo-WS] Listener started on ws://{host}:{port}")

    async def send_command_async(self, session_id, command_dict):
        if session_id not in self.active_sessions:
            return {"status": "error", "message": f"Session {session_id} not found."}
        
        ws = self.active_sessions[session_id]
        queue = self.queues[session_id]
        
        # 清除舊的回應
        while not queue.empty(): queue.get_nowait()
        
        await ws.send(json.dumps(command_dict))
        
        try:
            res = await asyncio.wait_for(queue.get(), timeout=15.0)
            with self._lock:
                if session_id in self.session_info:
                    self.session_info[session_id]["stats"]["cmds"] += 1
            return res
        except asyncio.TimeoutError:
            with self._lock:
                if session_id in self.session_info:
                    self.session_info[session_id]["stats"]["errors"] += 1
            return {"status": "error", "message": "Dynamo response timeout."}

    async def cleanup_stale_sessions(self, timeout=30.0):
        """自動清理超過超時時間未反應的會話"""
        now = time.time()
        to_remove = []
        with self._lock:
            for sid, info in self.session_info.items():
                if now - info["lastSeen"] > timeout:
                    to_remove.append(sid)
        
        for sid in to_remove:
            log(f"[Dynamo-WS] Pruning stale session: {sid}")
            ws = self.active_sessions.get(sid)
            if ws: await ws.close()
            await self.unregister(sid)
        return len(to_remove)

ws_manager = WebSocketManager()

# ==========================================
# MCP Tools Bridge Server (WebSocket for Node.js)
# ==========================================

class MCPBridgeServer:
    """處理來自 Node.js MCP Server 的 WebSocket 請求"""
    
    def __init__(self, host="127.0.0.1", port=5051):
        self.host = host
        self.port = port

    async def serve(self):
        log(f"[MCP Bridge] Server starting on ws://{self.host}:{self.port}")
        async with websockets.serve(self._handle_bridge_client, self.host, self.port):
            await asyncio.Future()

    async def _handle_bridge_client(self, websocket):
        log(f"[MCP Bridge] Node.js client connected")
        try:
            async for message in websocket:
                try:
                    request = json.loads(message)
                    
                    # 驗證 JSON-RPC 2.0 格式
                    if request.get("jsonrpc") != "2.0":
                        log(f"[WARN] Invalid JSON-RPC version: {request.get('jsonrpc')}")
                    
                    method = request.get("method")
                    params = request.get("params", {})
                    request_id = request.get("id")  # 使用 id 而非 requestId

                    log(f"[MCP Bridge] Received: {method}")

                    # Handle request
                    if method == "tools/list":
                        result = await self._list_tools()
                    elif method == "tools/call":
                        result = await self._call_tool(params)
                    else:
                        result = {"error": f"Unknown method: {method}"}

                    # Send response (JSON-RPC 2.0 格式)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }
                    await websocket.send(json.dumps(response, ensure_ascii=False))

                except Exception as e:
                    log(f"[MCP Bridge] Request error: {e}")
                    # JSON-RPC 2.0 錯誤格式
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {
                            "code": -32603,  # Internal error
                            "message": str(e)
                        }
                    }
                    await websocket.send(json.dumps(error_response))

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            log("[MCP Bridge] Node.js client disconnected")

    async def _list_tools(self):
        """返回可用工具列表"""
        tools = [
            {
                "name": "execute_dynamo_instructions",
                "description": "在 Dynamo 中執行節點創建指令。instructions 參數必須是 JSON 字串，包含 'nodes' 陣列（節點定義）和 'connectors' 陣列（連線定義）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instructions": {
                            "type": "string",
                            "description": "JSON 格式的完整圖形定義。必須包含兩個欄位：'nodes'（節點陣列）和 'connectors'（連線陣列）。"
                        },
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定要執行的會話 ID。若未指定則使用最新連線。"
                        }
                    },
                    "required": ["instructions"]
                },
                "destructiveHint": True
            },
            {
                "name": "analyze_workspace",
                "description": "取得 Dynamo 工作區中所有節點的當前狀態。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "get_graph_status",
                "description": "取得工作區圖表完整狀態 JSON。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "clear_workspace",
                "description": "清除工作區內容。",
                "inputSchema": {"type": "object", "properties": {}},
                "destructiveHint": True
            },
            {
                "name": "search_nodes",
                "description": "在 Dynamo 庫中搜尋節點。這會返回節點的 fullName，可用於 execute_dynamo_instructions。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜尋關鍵字（例如 'Room', 'Solid', 'Point'）"
                        }
                    },
                    "required": ["query"]
                },
                "readOnlyHint": True
            },
            {
                "name": "get_mcp_guidelines",
                "description": "取得規範內容。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "get_script_library",
                "description": "取得腳本庫清單。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "list_sessions",
                "description": "列出所有當前活動中的 Dynamo WebSocket 會話及其詳細資訊。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "get_server_stats",
                "description": "取得 Bridge Server 的運行數據與效能統計。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
        ]
        return tools

    async def _call_tool(self, params):
        """執行工具呼叫"""
        name = params.get("name")
        args = params.get("arguments", {})
        
        try:
            if name == "execute_dynamo_instructions":
                return await execute_dynamo_instructions(**args)
            elif name == "search_nodes":
                return await search_nodes_async(**args)
            elif name == "analyze_workspace":
                return await analyze_workspace()
            elif name == "get_graph_status":
                _, res = await _check_dynamo_connection()
                return res
            elif name == "clear_workspace":
                return await clear_workspace()
            elif name == "get_mcp_guidelines":
                return get_mcp_guidelines()
            elif name == "get_script_library":
                return get_script_library()
            elif name == "list_sessions":
                return await list_sessions()
            elif name == "get_server_stats":
                return get_server_stats()
            else:
                return {"error": f"Tool not found: {name}"}
        except Exception as e:
            return {"error": str(e)}

# ==========================================
# 工具實作
# ==========================================

async def _check_dynamo_connection(session_id: str = None) -> tuple[bool, str]:
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
    if not sessions: return False, "No active Dynamo connections."
    
    if session_id and session_id not in sessions:
        return False, f"Specified session {session_id} not found."
    
    target_id = session_id if session_id else sessions[-1]
    try:
        data = await ws_manager.send_command_async(target_id, {"action": "get_graph_status"})
        if data.get("status") == "error": return False, data.get("message")
        return True, json.dumps(data, ensure_ascii=False)
    except Exception as e: 
        return False, str(e)

# ==========================================
# 節點擴展與降級邏輯 (Optimization v1.2)
# ==========================================

def _generate_ds_code(node: dict) -> str:
    """將原生節點規範轉換為 DesignScript 代碼 (用於軌道 A 降級)"""
    name = node.get("name", "")
    params = node.get("params", {})
    
    # 處理特殊節點
    if name == "Number" or name == "Code Block":
        val = str(node.get("value", "0"))
        return val if val.endswith(";") else val + ";"
        
    # 格式化參數
    param_strs = []
    metadata = _load_common_nodes_metadata()
    node_info = metadata.get(name, {})
    input_keys = node_info.get("inputs", list(params.keys()))
    
    for key in input_keys:
        if key in params:
            val = params[key]
            # 簡單判斷是否為字串
            if isinstance(val, str) and not (val.replace('.','',1).isdigit() or val.startswith("Point.") or val.startswith("Vector.") or val.startswith("[") or val.endswith(";")):
                param_strs.append(f"\"{val}\"")
            else:
                param_strs.append(str(val))
    
    return f"{name}({', '.join(param_strs)});"

def _expand_native_nodes(instruction: dict) -> dict:
    """自動將帶 params 的原生節點擴展為 Number 節點 + Connectors (軌道 B)"""
    nodes = instruction.get("nodes", [])
    connectors = instruction.get("connectors", [])
    expanded_nodes = []
    expanded_connectors = list(connectors)
    
    metadata = _load_common_nodes_metadata()
    import time
    timestamp = int(time.time() * 1000)
    
    for node in nodes:
        name = node.get("name", "")
        params = node.get("params", {})
        node_id = node.get("id", str(uuid.uuid4()))
        
        # 只有在 metadata 中且有 params 時才擴展
        if name in metadata and params:
            node_info = metadata[name]
            input_ports = node_info.get("inputs", [])
            
            # 為每個參數創建 Number 節點
            for i, port_name in enumerate(input_ports):
                if port_name in params:
                    param_id = f"{node_id}_{port_name}_{timestamp}"
                    param_node = {
                        "id": param_id,
                        "name": "Number",
                        "value": str(params[port_name]),
                        "x": float(node.get("x", 0)) - 250,
                        "y": float(node.get("y", 0)) + (i * 80),
                        "preview": node.get("preview", True)
                    }
                    expanded_nodes.append(param_node)
                    
                    # 建立連線 (同時包含索引與名稱，提供 Fallback 能力)
                    expanded_connectors.append({
                        "from": param_id,
                        "to": node_id,
                        "fromPort": 0,
                        "toPort": i,
                        "toPortName": port_name
                    })
            
            # 清除原 node 的 params 避免重複處理
            clean_node = {k: v for k, v in node.items() if k != "params"}
            expanded_nodes.append(clean_node)
        else:
            expanded_nodes.append(node)
            
    return {"nodes": expanded_nodes, "connectors": expanded_connectors}

async def execute_dynamo_instructions(instructions: str, clear_before_execute: bool = False, base_x: float = 0, base_y: float = 0, allow_fallback: bool = True, sessionId: str = None) -> str:
    with ws_manager._lock: sessions = list(ws_manager.active_sessions.keys())
    if not sessions: return "❌ 失敗: 未連線"
    
    if sessionId and sessionId not in sessions:
        return f"❌ 失敗: 找不到指定的會話 {sessionId}"
    
    session_id = sessionId if sessionId else sessions[-1]
    try:
        # 1. 解析與驗證 JSON
        try:
            json_data = json.loads(instructions)
        except json.JSONDecodeError as e:
            return f"❌ JSON 解析錯誤: {str(e)}"
        
        if isinstance(json_data, list):
            json_data = {"nodes": json_data, "connectors": []}
            
        # 2. 軌道 B 自動擴展
        json_data = _expand_native_nodes(json_data)
        
        # 3. 座標偏移與策略標註
        if "nodes" in json_data:
            for node in json_data["nodes"]:
                route_node_creation(node)
                node["x"] = float(node.get("x", 0)) + base_x
                node["y"] = float(node.get("y", 0)) + base_y
        
        if clear_before_execute: 
            await ws_manager.send_command_async(session_id, {"action": "clear_graph"})
        
        # 4. 首次嘗試執行
        response = await ws_manager.send_command_async(session_id, json_data)
        
        # 5. [核心優化] 差異化重試與降級機制 (Differentiated Fallback)
        if response.get("status") == "error" and allow_fallback:
            log(f"[Fallback] 軌道 B 執行失敗，嘗試降級至軌道 A (Code Block)... 錯誤: {response.get('message')}")
            
            fallback_nodes = []
            for node in json_data.get("nodes", []):
                # 僅針對原生幾何節點進行轉換
                if node.get("name") in _load_common_nodes_metadata():
                    code = _generate_ds_code(node)
                    fallback_node = {
                        "id": node.get("id"),
                        "name": "Number",
                        "value": code,
                        "x": node.get("x"),
                        "y": node.get("y"),
                        "preview": node.get("preview", True)
                    }
                    fallback_nodes.append(fallback_node)
                else:
                    # 非原生節點保留（例如 Python Script 保持不變，或已轉換的 Number 節點）
                    fallback_nodes.append(node)
            
            # 建立降級後的指令集（通常 Code Block 模式不依賴 connectors，因為邏輯已內嵌）
            # 但如果是手動指定的連線仍需保留
            fallback_data = {
                "nodes": fallback_nodes,
                "connectors": json_data.get("connectors", []) if not any(n.get("name") in _load_common_nodes_metadata() for n in json_data.get("nodes", [])) else []
            }
            
            retry_response = await ws_manager.send_command_async(session_id, fallback_data)
            if retry_response.get("status") == "ok":
                return "✅ 成功 (已透過軌道 A 降級重試恢復)"
            else:
                return f"❌ 失敗 (重試後仍錯誤): {retry_response.get('message')}"
        
        return f"✅ 成功" if response.get("status") == "ok" else f"❌ 失敗: {response.get('message')}"
    except Exception as e: 
        return f"Error: {e}"

async def search_nodes_async(query: str) -> str:
    with ws_manager._lock: sessions = list(ws_manager.active_sessions.keys())
    if not sessions: return "❌ 失敗: 未連線"
    session_id = sessions[-1]
    try:
        data = await ws_manager.send_command_async(session_id, {"action": "list_nodes", "filter": query})
        if data.get("status") == "error": return f"❌ 搜尋出錯: {data.get('message')}"
        
        # If the backend provided a formatted display string, use it
        if data.get("display"):
            return data["display"]

        nodes = data.get("nodes", [])
        if not nodes: return f"🔍 搜尋 '{query}': 找不到任何節點。"
        
        # Fallback formatting
        res = [f"🔍 搜尋 '{query}' 找到 {data.get('count', 0)} 個結果 (僅列出前 50 個):\n"]
        for n in nodes:
            res.append(f"- **{n['name']}**")
            res.append(f"  fullName: `{n['fullName']}`")
            if n.get('creationName'): res.append(f"  creationName: `{n['creationName']}`")
            if n.get('description'): res.append(f"  說明: {n['description']}")
            res.append("")
        return "\n".join(res)
    except Exception as e:
        return f"Error: {e}"

async def analyze_workspace() -> str:
    # 每次分析前清理過期會話
    await ws_manager.cleanup_stale_sessions()
    
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
        session_count = len(sessions)
        session_info = dict(ws_manager.session_info)
    
    is_ok, res = await _check_dynamo_connection()
    if not is_ok:
        return f"❌ 失敗: {res}"
    
    # [核心優化] 幽靈連線偵測與詳細狀態
    if session_count > 1:
        data = json.loads(res)
        data["warning"] = f"⚠️ 警告: 偵測到 {session_count} 個活動中的會話。指令目前預設發送至最後一個連線 (Session: {sessions[-1]})。若不正確，請使用 list_sessions 查看並指定 sessionId。"
        data["all_sessions"] = [
            {"id": sid, "fileName": info["fileName"], "connected": time.strftime('%H:%M:%S', time.localtime(info['connectedAt']))}
            for sid, info in session_info.items()
        ]
        return json.dumps(data, ensure_ascii=False)
        
    return res

async def list_sessions() -> str:
    """提供可讀性高的會話列表"""
    with ws_manager._lock:
        sessions = dict(ws_manager.session_info)
    
    if not sessions: return "📭 目前沒有活動中的會話。"
    
    lines = ["📋 活動中的 Dynamo 會話清單：\n"]
    for i, (sid, info) in enumerate(sessions.items()):
        status = "🟢 作用中" if (time.time() - info["lastSeen"]) < 10 else "🟡 閒置"
        lines.append(f"{i+1}. **{info['fileName']}**")
        lines.append(f"   - SessionID: `{sid}`")
        lines.append(f"   - 狀態: {status} (最後活動: {int(time.time() - info['lastSeen'])} 秒前)")
        lines.append(f"   - 連線時間: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['connectedAt']))}")
        lines.append(f"   - 累積指令數: {info['stats']['cmds']} | 錯誤數: {info['stats']['errors']}")
        lines.append("")
        
    return "\n".join(lines)

def get_server_stats() -> dict:
    """提供效能監控數據 (Performance Dashboard)"""
    with ws_manager._lock:
        total_sessions = len(ws_manager.active_sessions)
        total_cmds = sum(s["stats"]["cmds"] for s in ws_manager.session_info.values())
        uptime = int(time.time() - ws_manager.start_time)
        
    return {
        "status": "Running",
        "uptime_seconds": uptime,
        "active_sessions": total_sessions,
        "total_commands_processed": total_cmds,
        "bridge_port": 65296,
        "dynamo_port": ws_manager.port
    }

async def clear_workspace() -> str:
    with ws_manager._lock: sessions = list(ws_manager.active_sessions.keys())
    if not sessions: return "❌ 失敗"
    res = await ws_manager.send_command_async(sessions[-1], {"action": "clear_graph"})
    return "✅ 已清空" if res.get("status") == "ok" else f"❌ 失敗"

def get_mcp_guidelines() -> str:
    g, q = _load_guidelines()
    return f"# GUIDELINES\\n\\n{g}\\n\\n# QUICK REF\\n\\n{q}"

def get_script_library() -> str:
    scripts = []
    for f in glob.glob(os.path.join(SCRIPT_DIR, "*.json")):
        name = os.path.basename(f).replace(".json", "")
        try:
            with open(f, "r", encoding="utf-8") as rf: 
                desc = json.load(rf).get("description", "No description")
        except: 
            desc = "No description"
        scripts.append({"name": name, "description": desc})
    return json.dumps(scripts, ensure_ascii=False, indent=2)

# ==========================================
# 入口點
# ==========================================

if __name__ == "__main__":
    log("═══════════════════════════════════════════")
    log("  Dynamo WebSocket Manager (Python)")
    log("═══════════════════════════════════════════")
    log("")
    
    # 啟動 Dynamo Listener (websocket_port: 65535 - C# Extension 連線)
    dynamo_port = CONFIG.get("server", {}).get("websocket_port", 65535)
    ws_manager.start_server("127.0.0.1", dynamo_port)
    
    # 啟動 MCP Bridge Server (port 65296 - 供 Node.js MCP Server 連線)
    bridge_server = MCPBridgeServer(port=65296)
    
    try:
        asyncio.run(bridge_server.serve())
    except KeyboardInterrupt:
        log("Server stopped by user.")
