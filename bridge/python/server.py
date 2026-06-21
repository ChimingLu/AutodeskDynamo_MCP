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

import time, os, json, glob, asyncio, websockets, threading, uuid, subprocess, sys, re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from pathlib import Path
from collections import Counter

# 全域日誌函數
def log(m): print(m, file=sys.stderr)

# ==========================================
# 多客戶端衝突協調層 (Conflict Coordination Layer)
# ==========================================

class WorkspaceState:
    """
    工作區版本控制 - 實作樂觀鎖機制
    每個 Session 獨立追蹤版本號，避免多 AI 客戶端衝突
    """
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.version = 0
        self.last_writer = None
        self.last_write_time = 0
        self._lock = asyncio.Lock()
    
    async def acquire_write(self, client_id: str, expected_version: int = None) -> tuple:
        """
        嘗試取得寫入權限
        Returns: (success: bool, result: dict)
        """
        async with self._lock:
            if expected_version is not None and expected_version != self.version:
                return False, {
                    "status": "version_conflict",
                    "message": f"版本衝突：預期 {expected_version}，實際 {self.version}。請重新讀取工作區狀態後再試。",
                    "currentVersion": self.version,
                    "lastWriter": self.last_writer,
                    "lastWriteTime": self.last_write_time
                }
            
            self.version += 1
            self.last_writer = client_id
            self.last_write_time = time.time()
            return True, {"newVersion": self.version}
    
    def get_version(self) -> int:
        return self.version
    
    def get_info(self) -> dict:
        return {
            "sessionId": self.session_id,
            "version": self.version,
            "lastWriter": self.last_writer,
            "lastWriteTime": self.last_write_time
        }

class SessionStateManager:
    """管理多個 Session 的版本控制"""
    def __init__(self):
        self._states: Dict[str, WorkspaceState] = {}
        self._lock = threading.Lock()
    
    def get_state(self, session_id: str) -> WorkspaceState:
        with self._lock:
            if session_id not in self._states:
                self._states[session_id] = WorkspaceState(session_id)
            return self._states[session_id]
    
    def remove_state(self, session_id: str):
        with self._lock:
            if session_id in self._states:
                del self._states[session_id]

# 全域 Session 狀態管理器
session_state_manager = SessionStateManager()

# ==========================================
# 基礎路徑與設定
# ==========================================
GUIDELINE_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "GEMINI.md"))
QUICK_REF_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "QUICK_REFERENCE.md"))
CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp_config.json"))
ADDON_GUID_MAPPING_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "domain", "addon_guid_mapping.json"))
MEMORY_BANK_PATH = Path(__file__).parent.parent.parent / "memory-bank"

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
# Memory Bank 快取系統（混合策略）
# ==========================================

# 全域快取變數
MEMORY_BANK_SUMMARY = None
MEMORY_BANK_LOAD_TIME = None

def _read_file_safe(file_path: Path) -> str:
    """安全讀取檔案，失敗回傳空字串"""
    try:
        if file_path.exists():
            return file_path.read_text(encoding='utf-8')
        return ""
    except Exception as e:
        log(f"[WARN] Failed to read {file_path}: {e}")
        return ""

def _load_lessons(lessons_path: Path) -> list:
    """載入所有 lessons/*.md 檔案標題與摘要"""
    if not lessons_path.exists():
        return []
    
    lessons = []
    for md_file in sorted(lessons_path.glob("*.md")):
        content = _read_file_safe(md_file)
        if not content:
            continue
        
        # 提取第一行標題與前 10 行作為摘要
        lines = content.split('\n')
        title = lines[0].strip('# ').strip() if lines else md_file.stem
        summary = '\n'.join(lines[:10])
        
        lessons.append({
            "file": md_file.name,
            "title": title,
            "summary": summary
        })
    
    return lessons

def load_memory_bank() -> dict:
    """
    啟動時讀取並快取 memory-bank/ 資料夾摘要
    Returns: 載入狀態字典
    """
    global MEMORY_BANK_SUMMARY, MEMORY_BANK_LOAD_TIME
    
    if not MEMORY_BANK_PATH.exists():
        log("[WARN] memory-bank/ directory not found")
        MEMORY_BANK_SUMMARY = {"status": "error", "message": "memory-bank 資料夾不存在"}
        return MEMORY_BANK_SUMMARY
    
    try:
        log("[Memory Bank] Loading memory bank...")
        
        # 讀取核心文件
        summary = {
            "status": "ok",
            "loadTime": time.time(),
            "projectBrief": _read_file_safe(MEMORY_BANK_PATH / "projectbrief.md"),
            "productContext": _read_file_safe(MEMORY_BANK_PATH / "productContext.md"),
            "systemPatterns": _read_file_safe(MEMORY_BANK_PATH / "systemPatterns.md"),
            "techContext": _read_file_safe(MEMORY_BANK_PATH / "techContext.md"),
            "activeContext": _read_file_safe(MEMORY_BANK_PATH / "activeContext.md"),
            "progress": _read_file_safe(MEMORY_BANK_PATH / "progress.md"),
            "lessons": _load_lessons(MEMORY_BANK_PATH / "lessons")
        }
        
        MEMORY_BANK_SUMMARY = summary
        MEMORY_BANK_LOAD_TIME = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(summary["loadTime"]))
        
        log(f"[Memory Bank] ✅ Loaded {len(summary['lessons'])} lessons")
        log(f"[Memory Bank] Load time: {MEMORY_BANK_LOAD_TIME}")
        
        return {"status": "ok", "loadTime": MEMORY_BANK_LOAD_TIME, "lessonsCount": len(summary["lessons"])}
        
    except Exception as e:
        error_msg = f"Failed to load memory bank: {e}"
        log(f"[ERROR] {error_msg}")
        MEMORY_BANK_SUMMARY = {"status": "error", "message": error_msg}
        return MEMORY_BANK_SUMMARY

# ==========================================
# 工具邏輯與輔助函式
# ==========================================

_common_nodes_metadata = None
_addon_guid_mapping = None

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

def _load_addon_guid_mapping() -> dict:
    """載入外掛 GUID 映射檔，提供名稱->GUID 的快速查找。"""
    global _addon_guid_mapping
    if _addon_guid_mapping is not None:
        return _addon_guid_mapping

    empty = {"entries": [], "index": {}}
    if not os.path.exists(ADDON_GUID_MAPPING_PATH):
        _addon_guid_mapping = empty
        return _addon_guid_mapping

    try:
        with open(ADDON_GUID_MAPPING_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)

        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        index = {}
        normalized_entries = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            guid = str(entry.get("guid", "")).strip().lower()
            if not guid:
                continue

            package = str(entry.get("package", "")).strip()
            node_display = str(entry.get("nodeDisplay", "")).strip()

            normalized = {
                "package": package,
                "nodeDisplay": node_display,
                "guid": guid,
                "note": entry.get("note", ""),
                "source": entry.get("source", "")
            }
            normalized_entries.append(normalized)

            # 支援多種查詢鍵：GUID、顯示名稱、Package.Node、Package:Node
            alias_candidates = {
                guid,
                node_display.lower(),
                f"{package}.{node_display}".lower(),
                f"{package}:{node_display}".lower(),
            }
            for alias in alias_candidates:
                if alias and alias != ".":
                    index[alias] = normalized

        _addon_guid_mapping = {"entries": normalized_entries, "index": index, "entryCount": len(normalized_entries)}
        return _addon_guid_mapping
    except Exception as e:
        log(f"[WARN] Failed to load addon guid mapping: {e}")
        _addon_guid_mapping = {**empty, "entryCount": 0}
        return _addon_guid_mapping


def _load_workspace_snapshot(snapshot_path: str) -> dict:
    """從離線 JSON 快照載入工作區資料。"""
    if not snapshot_path:
        raise ValueError("snapshotPath is required")

    path = Path(snapshot_path)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Snapshot JSON must be an object")
    return raw


def _coerce_workspace_payload(raw: dict) -> dict:
    """正規化即時工作區與離線快照的欄位結構。"""
    workspace = raw.get("workspace") if isinstance(raw.get("workspace"), dict) else {}
    nodes = raw.get("nodes", []) if isinstance(raw.get("nodes"), list) else []
    connectors = raw.get("connectors", []) if isinstance(raw.get("connectors"), list) else []

    workspace_name = (
        workspace.get("name")
        or raw.get("workspaceName")
        or Path(workspace.get("fileName", "")).stem
        or "Home"
    )
    file_name = workspace.get("fileName") or raw.get("fileName") or ""

    return {
        "sessionId": raw.get("sessionId"),
        "processId": raw.get("processId"),
        "workspace": {
            "name": workspace_name,
            "fileName": file_name,
        },
        "workspaceName": workspace_name,
        "nodeCount": raw.get("nodeCount", len(nodes)),
        "connectorCount": raw.get("connectorCount", len(connectors)),
        "nodes": nodes,
        "connectors": connectors,
        "warning": raw.get("warning"),
        "all_sessions": raw.get("all_sessions", []),
    }


async def _get_workspace_payload(session_id: str = None, snapshot_path: str = None) -> dict:
    if snapshot_path:
        return _coerce_workspace_payload(_load_workspace_snapshot(snapshot_path))

    ok, res = await _check_dynamo_connection(session_id=session_id)
    if not ok:
        raise RuntimeError(res)

    if isinstance(res, str):
        return _coerce_workspace_payload(json.loads(res))
    return _coerce_workspace_payload(res)


def _sanitize_mermaid_id(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "node"))
    if not token or token[0].isdigit():
        token = f"n_{token}"
    return token


def _sanitize_mermaid_label(value: str, limit: int = 40) -> str:
    text = str(value or "(unnamed)").replace('"', "'").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _extract_node_type(node: dict) -> str:
    full_name = str(node.get("fullName") or "")
    if full_name:
        return full_name.split(".")[-1]
    return str(node.get("name") or "Unknown")


def _classify_workspace_node(node: dict, indegree: int, outdegree: int) -> str:
    full_name = str(node.get("fullName") or "")
    name = str(node.get("name") or "")
    lowered = f"{name} {full_name}".lower()

    if any(full_name.startswith(prefix) for prefix in _INPUT_PREFIXES):
        return "input"
    if any(full_name.startswith(prefix) for prefix in _OUTPUT_FULL) or name in _OUTPUT_NAMES:
        return "output"
    if any(keyword in lowered for keyword in ["select", "input", "slider", "boolean", "string", "number"]):
        return "input"
    if outdegree == 0:
        return "output"
    if indegree == 0:
        return "input"
    return "compute"


def _workspace_complexity_rating(node_count: int, connector_count: int) -> tuple[str, str]:
    score = node_count + connector_count
    if score >= 180:
        return "高", "⭐⭐⭐⭐⭐"
    if score >= 100:
        return "中高", "⭐⭐⭐⭐"
    if score >= 50:
        return "中", "⭐⭐⭐"
    if score >= 20:
        return "低中", "⭐⭐"
    return "低", "⭐"


def _summarize_workspace_steps(nodes: list, connectors: list, focus_ids: set) -> list:
    if not nodes:
        return []

    outgoing = {node.get("id"): [] for node in nodes}
    incoming = {node.get("id"): [] for node in nodes}
    for connector in connectors:
        source = connector.get("from")
        target = connector.get("to")
        if source in outgoing:
            outgoing[source].append(target)
        if target in incoming:
            incoming[target].append(source)

    input_nodes = [node for node in nodes if node.get("category") == "input" and node.get("id") in focus_ids]
    compute_nodes = [node for node in nodes if node.get("category") == "compute" and node.get("id") in focus_ids]
    output_nodes = [node for node in nodes if node.get("category") == "output" and node.get("id") in focus_ids]

    steps = []
    if input_nodes:
        labels = "、".join(_sanitize_mermaid_label(node.get("name"), 18) for node in input_nodes[:4])
        steps.append(f"收集輸入：由 {labels} 等節點提供參數或模型來源。")

    if compute_nodes:
        ranked = sorted(
            compute_nodes,
            key=lambda node: len(outgoing.get(node.get("id"), [])) + len(incoming.get(node.get("id"), [])),
            reverse=True,
        )
        labels = "、".join(_sanitize_mermaid_label(node.get("name"), 18) for node in ranked[:4])
        steps.append(f"核心運算：主要透過 {labels} 串接資料轉換與幾何/邏輯處理。")

    if output_nodes:
        labels = "、".join(_sanitize_mermaid_label(node.get("name"), 18) for node in output_nodes[:4])
        steps.append(f"輸出結果：最終流向 {labels} 等終端節點供觀察或後續使用。")

    return steps


def _select_focus_nodes(nodes: list, connectors: list, max_nodes: int) -> tuple[list, bool]:
    if len(nodes) <= max_nodes:
        return nodes, False

    indegree = Counter()
    outdegree = Counter()
    for connector in connectors:
        outdegree[connector.get("from")] += 1
        indegree[connector.get("to")] += 1

    def priority(node: dict) -> tuple:
        node_id = node.get("id")
        name = str(node.get("name") or "")
        category = node.get("category")
        degree = indegree[node_id] + outdegree[node_id]
        special = 1 if name in {"Python Script", "Watch", "Watch 3D"} else 0
        return (
            1 if category == "input" else 0,
            1 if category == "output" else 0,
            special,
            degree,
        )

    selected = sorted(nodes, key=priority, reverse=True)[:max_nodes]
    selected_ids = {node.get("id") for node in selected}
    connected = [
        connector for connector in connectors
        if connector.get("from") in selected_ids and connector.get("to") in selected_ids
    ]

    referenced_ids = {connector.get("from") for connector in connected} | {connector.get("to") for connector in connected}
    pruned = [node for node in selected if node.get("id") in referenced_ids or node.get("category") != "compute"]
    return pruned[:max_nodes], True


def _build_mermaid_flowchart(nodes: list, connectors: list, direction: str) -> str:
    """原始 1:1 對應版本（供 debug/詳細檢視使用）。"""
    lines = [f"flowchart {direction}"]
    category_titles = {
        "input": "輸入 / Sources",
        "compute": "核心運算 / Logic",
        "output": "輸出 / Sinks",
    }

    nodes_by_category = {"input": [], "compute": [], "output": []}
    for node in nodes:
        nodes_by_category.setdefault(node.get("category"), []).append(node)

    for category in ["input", "compute", "output"]:
        lines.append(f"    subgraph {category}[\"{category_titles[category]}\"]")
        for node in nodes_by_category.get(category, []):
            mermaid_id = _sanitize_mermaid_id(node.get("id"))
            label = _sanitize_mermaid_label(node.get("name") or _extract_node_type(node))
            lines.append(f"        {mermaid_id}[\"{label}\"]")
        lines.append("    end")

    for connector in connectors:
        source = _sanitize_mermaid_id(connector.get("from"))
        target = _sanitize_mermaid_id(connector.get("to"))
        lines.append(f"    {source} --> {target}")

    lines.extend([
        "    classDef input fill:#14324a,stroke:#62b6ff,color:#ffffff;",
        "    classDef compute fill:#24341f,stroke:#8ed081,color:#ffffff;",
        "    classDef output fill:#4a2614,stroke:#ffb366,color:#ffffff;",
    ])

    for category in ["input", "compute", "output"]:
        ids = [_sanitize_mermaid_id(node.get("id")) for node in nodes_by_category.get(category, [])]
        if ids:
            lines.append(f"    class {','.join(ids)} {category};")

    return "\n".join(lines)


def _build_semantic_mermaid_flowchart(nodes: list, connectors: list, direction: str) -> str:
    """語意合併版本：同類型節點合成一格（如 Point.ByCoordinates ×8），
    同類型間的邊去重，輸出可讀邏輯流程圖。"""
    category_titles = {
        "input": "輸入 / Sources",
        "compute": "核心運算 / Logic",
        "output": "輸出 / Sinks",
    }

    # node_id -> group_key (category__typename)
    node_id_to_group: dict[str, str] = {}
    groups: dict[str, dict] = {}  # group_key -> {id, label, category, count}

    for node in nodes:
        # 優先用 node.name（使用者看到的顯示名稱，如 Point.ByCoordinates）
        # 次選 fullName 的最後一段，最後才用內部 type
        display_name = str(node.get("name") or "").strip()
        if not display_name:
            full_name = str(node.get("fullName") or "")
            display_name = full_name.split(".")[-1] if full_name else _extract_node_type(node)
        cat = node.get("category", "compute")
        safe_key = re.sub(r"[^A-Za-z0-9_]", "_", display_name)
        group_key = f"{cat}__{safe_key}"

        node_id_to_group[node.get("id", "")] = group_key

        if group_key not in groups:
            groups[group_key] = {
                "id": group_key,
                "label": display_name,
                "category": cat,
                "count": 0,
            }
        groups[group_key]["count"] += 1

    # 有多個實例時加上數量標記
    for g in groups.values():
        if g["count"] > 1:
            g["label"] = f"{g['label']} \u00d7{g['count']}"

    # 建立去重後的 group 間連線
    edges: set[tuple[str, str]] = set()
    for connector in connectors:
        src = node_id_to_group.get(connector.get("from", ""))
        tgt = node_id_to_group.get(connector.get("to", ""))
        if src and tgt and src != tgt:
            edges.add((src, tgt))

    lines = [f"flowchart {direction}"]
    groups_by_cat: dict[str, list] = {"input": [], "compute": [], "output": []}
    for g in groups.values():
        groups_by_cat.setdefault(g["category"], []).append(g)

    for category in ["input", "compute", "output"]:
        cat_groups = groups_by_cat.get(category, [])
        if not cat_groups:
            continue
        lines.append(f"    subgraph {category}[\"{category_titles[category]}\"]")
        for g in cat_groups:
            lines.append(f"        {g['id']}[\"{g['label']}\"]")
        lines.append("    end")

    for src, tgt in sorted(edges):
        lines.append(f"    {src} --> {tgt}")

    lines.extend([
        "    classDef input fill:#14324a,stroke:#62b6ff,color:#ffffff;",
        "    classDef compute fill:#24341f,stroke:#8ed081,color:#ffffff;",
        "    classDef output fill:#4a2614,stroke:#ffb366,color:#ffffff;",
    ])
    for category in ["input", "compute", "output"]:
        ids = [g["id"] for g in groups_by_cat.get(category, []) if g]
        if ids:
            lines.append(f"    class {','.join(ids)} {category};")

    return "\n".join(lines)


def _build_pipeline_mermaid_flowchart(nodes: list, connectors: list, direction: str) -> str:
    """Pipeline 階段式流程圖（預設最可讀版本）。

    流程：
    1. 每個節點依 _assign_pipeline_stage 分配至工作流階段。
    2. BFS 拓撲排序決定各階段的先後順序。
    3. 每個階段合成一個方框，標籤為「中文描述 NodeA / NodeB ...」。
    4. 跨階段連線去重後繪製。
    """
    # ── 1. 分配 stage ──────────────────────────────────────────────
    id_to_stage: dict[str, str] = {}
    stage_names: dict[str, set[str]] = {}   # stage_key -> 唯一顯示名稱集合

    for node in nodes:
        stage = _assign_pipeline_stage(node)
        nid = node.get("id", "")
        id_to_stage[nid] = stage
        display = str(node.get("name") or "").strip()
        if display:
            stage_names.setdefault(stage, set()).add(display)

    # ── 2. 拓撲 BFS 取得各節點深度 ─────────────────────────────────
    all_ids = {n.get("id") for n in nodes}
    from_map: dict[str, list[str]] = {}
    in_deg: Counter = Counter()
    for c in connectors:
        src, tgt = c.get("from", ""), c.get("to", "")
        if src in all_ids and tgt in all_ids:
            from_map.setdefault(src, []).append(tgt)
            in_deg[tgt] += 1

    depth: dict[str, int] = {}
    queue = [nid for nid in all_ids if in_deg[nid] == 0]
    for nid in queue:
        depth[nid] = 0
    visited: set[str] = set(queue)
    while queue:
        nxt: list[str] = []
        for nid in queue:
            for tgt in from_map.get(nid, []):
                if tgt not in visited:
                    visited.add(tgt)
                    depth[tgt] = depth.get(nid, 0) + 1
                    nxt.append(tgt)
        queue = nxt

    # ── 3. 各階段的「代表深度」（中位數）→ 決定圖中由左到右/由上到下的順序 ──
    stage_depths: dict[str, list[int]] = {}
    for nid, stage in id_to_stage.items():
        stage_depths.setdefault(stage, []).append(depth.get(nid, 0))

    stage_order = sorted(
        stage_names.keys(),
        key=lambda s: sorted(stage_depths.get(s, [0]))[len(stage_depths.get(s, [0])) // 2]
    )

    # ── 4. 建立去重的階段間連線，並移除會造成循環的反向邊 ────────────
    # 先依 stage_order 建立位置索引，只保留 src 位置 < tgt 位置的「前向邊」
    stage_rank: dict[str, int] = {s: i for i, s in enumerate(stage_order)}

    stage_edges: set[tuple[str, str]] = set()
    for c in connectors:
        src_s = id_to_stage.get(c.get("from", ""))
        tgt_s = id_to_stage.get(c.get("to", ""))
        if src_s and tgt_s and src_s != tgt_s:
            # 只接受前向邊（stage rank 較小 → 較大）
            if stage_rank.get(src_s, 0) < stage_rank.get(tgt_s, 0):
                stage_edges.add((src_s, tgt_s))

    # ── 5. 組裝 Mermaid ────────────────────────────────────────────
    # 階段 → Mermaid 節點 ID（安全字元）
    safe_id: dict[str, str] = {s: re.sub(r"[^A-Za-z0-9_]", "_", s) for s in stage_order}

    # 顏色分類（用於 classDef）
    _stage_color_cls = {
        "input":           "inp",
        "revit_model":     "inp",
        "point_ops":       "cmp",
        "curve_ops":       "cmp",
        "data_assembly":   "cmp",
        "solid_ops":       "cmp",
        "surface_ops":     "cmp",
        "surface_analysis":"cmp",
        "output_geometry": "out",
        "observation":     "out",
    }

    lines = [f"flowchart {direction}"]
    stage_cls: dict[str, list[str]] = {"inp": [], "cmp": [], "out": []}

    for stage in stage_order:
        zh = _STAGE_LABELS_ZH.get(stage, stage)
        names_sorted = sorted(stage_names.get(stage, set()))
        # 去掉過長或重複意義的名稱，最多保留 5 個
        if len(names_sorted) > 5:
            names_sorted = names_sorted[:5]
        name_part = " / ".join(names_sorted)
        label = f"{zh} {name_part}".strip()
        if len(label) > 90:
            label = label[:87] + "..."
        mermaid_id = safe_id[stage]
        lines.append(f"    {mermaid_id}[\"{label}\"]")
        cls_key = _stage_color_cls.get(stage, "cmp")
        stage_cls[cls_key].append(mermaid_id)

    lines.append("")
    for src_s, tgt_s in sorted(stage_edges):
        if safe_id.get(src_s) and safe_id.get(tgt_s):
            lines.append(f"    {safe_id[src_s]} --> {safe_id[tgt_s]}")

    lines.extend([
        "    classDef inp fill:#14324a,stroke:#62b6ff,color:#ffffff;",
        "    classDef cmp fill:#24341f,stroke:#8ed081,color:#ffffff;",
        "    classDef out fill:#4a2614,stroke:#ffb366,color:#ffffff;",
    ])
    for cls_key, ids in stage_cls.items():
        if ids:
            lines.append(f"    class {','.join(ids)} {cls_key};")

    return "\n".join(lines)


def _build_workspace_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# {summary['workspace_name']} 腳本邏輯分析",
        "",
        f"> 生成時間：{summary['generated_at']}",
        f"> 資料來源：{summary['source']}",
        "",
        "## 概況",
        f"- 檔名：{summary['file_name'] or 'Home'}",
        f"- 節點數：{summary['node_count']}",
        f"- 連線數：{summary['connector_count']}",
        f"- 複雜度：{summary['complexity_label']} {summary['complexity_stars']}",
    ]

    if summary.get("warning"):
        lines.append(f"- 警告：{summary['warning']}")

    lines.extend([
        "",
        "## 邏輯摘要",
    ])
    for index, step in enumerate(report["logic_steps"], 1):
        lines.append(f"{index}. {step}")

    lines.extend([
        "",
        "## 主要節點類型",
    ])
    for item in report["top_node_types"]:
        lines.append(f"- {item['type']}: {item['count']} 個")

    lines.extend([
        "",
        "## Mermaid",
        "```mermaid",
        report["mermaid"],
        "```",
    ])

    if report["focus_nodes"]:
        lines.extend([
            "",
            "## 節點摘錄",
            "| 類別 | 節點 | 類型 | 座標 |",
            "|:---|:---|:---|:---|",
        ])
        for node in report["focus_nodes"][:20]:
            lines.append(
                f"| {node['category']} | {node['name']} | {node['type']} | ({node['x']}, {node['y']}) |"
            )

    return "\n".join(lines)


def _build_workspace_logic_report(payload: dict, direction: str = "LR", max_nodes: int = 60, mode: str = "pipeline") -> dict:
    nodes = payload.get("nodes", [])
    connectors = payload.get("connectors", [])
    node_map = {node.get("id"): dict(node) for node in nodes}

    indegree = Counter()
    outdegree = Counter()
    for connector in connectors:
        outdegree[connector.get("from")] += 1
        indegree[connector.get("to")] += 1

    for node_id, node in node_map.items():
        node["category"] = _classify_workspace_node(node, indegree[node_id], outdegree[node_id])

    classified_nodes = sorted(node_map.values(), key=lambda node: (node.get("category"), node.get("x", 0), node.get("y", 0)))
    focus_nodes, truncated = _select_focus_nodes(classified_nodes, connectors, max_nodes=max_nodes)
    focus_ids = {node.get("id") for node in focus_nodes}
    focus_connectors = [
        connector for connector in connectors
        if connector.get("from") in focus_ids and connector.get("to") in focus_ids
    ]

    type_counter = Counter(_extract_node_type(node) for node in classified_nodes)
    complexity_label, complexity_stars = _workspace_complexity_rating(payload.get("nodeCount", 0), payload.get("connectorCount", 0))

    report = {
        "summary": {
            "workspace_name": payload.get("workspaceName") or payload.get("workspace", {}).get("name") or "Home",
            "file_name": payload.get("workspace", {}).get("fileName") or "",
            "node_count": payload.get("nodeCount", len(nodes)),
            "connector_count": payload.get("connectorCount", len(connectors)),
            "complexity_label": complexity_label,
            "complexity_stars": complexity_stars,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "warning": payload.get("warning"),
            "source": "snapshot" if payload.get("processId") is None and payload.get("sessionId") is None else "live-workspace",
            "truncated": truncated,
        },
        "logic_steps": _summarize_workspace_steps(classified_nodes, connectors, focus_ids),
        "top_node_types": [
            {"type": node_type, "count": count}
            for node_type, count in type_counter.most_common(8)
        ],
        "focus_nodes": [
            {
                "id": node.get("id"),
                "name": _sanitize_mermaid_label(node.get("name"), 60),
                "type": _extract_node_type(node),
                "category": node.get("category"),
                "x": node.get("x", 0),
                "y": node.get("y", 0),
            }
            for node in focus_nodes
        ],
    }
    if mode == "detail":
        report["mermaid"] = _build_mermaid_flowchart(focus_nodes, focus_connectors, direction=direction)
    elif mode == "semantic":
        report["mermaid"] = _build_semantic_mermaid_flowchart(focus_nodes, focus_connectors, direction=direction)
    else:  # "pipeline" (default)
        report["mermaid"] = _build_pipeline_mermaid_flowchart(focus_nodes, focus_connectors, direction=direction)
    report["markdown"] = _build_workspace_markdown(report)
    return report


async def generate_workspace_mermaid(
    sessionId: str = None,
    snapshotPath: str = None,
    direction: str = "TD",
    maxNodes: int = 60,
    saveToFile: bool = False,
    outputPath: str = None,
    mode: str = "pipeline",
) -> dict:
    """分析當前 Dynamo 工作區並生成 Mermaid 流程圖與 Markdown 摘要。

    mode='pipeline'（預設）：工作流階段觀，自動分層並加中文描述，最可讀。
    mode='semantic'   ：同名節點合成一格加數量，適合中型圖。
    mode='detail'     ：每個 Dynamo 節點對應一格，供 debug。
    """
    direction = (direction or "TD").upper()
    if direction not in {"LR", "TD", "RL", "BT"}:
        return {"error": f"Unsupported direction: {direction}. Valid: LR, TD, RL, BT"}

    safe_mode = mode if mode in {"pipeline", "semantic", "detail"} else "pipeline"
    safe_max_nodes = max(10, min(int(maxNodes), 200))
    payload = await _get_workspace_payload(session_id=sessionId, snapshot_path=snapshotPath)
    if not payload.get("nodes"):
        return {"error": "Workspace is empty; no nodes available for analysis."}

    report = _build_workspace_logic_report(payload, direction=direction, max_nodes=safe_max_nodes, mode=safe_mode)

    if saveToFile:
        default_name = Path(report["summary"]["file_name"] or report["summary"]["workspace_name"] or "Home").stem or "Home"
        target = Path(outputPath) if outputPath else (Path(__file__).parent.parent.parent / "image" / f"{default_name}_logic_analysis.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report["markdown"], encoding="utf-8")
        report["savedTo"] = str(target)

    return report

def _is_guid_like(text: str) -> bool:
    try:
        uuid.UUID(str(text))
        return True
    except Exception:
        return False

def _resolve_addon_guid(name: str) -> Optional[dict]:
    if not name:
        return None
    if _is_guid_like(name):
        return None

    mapping = _load_addon_guid_mapping()
    index = mapping.get("index", {})

    key = str(name).strip().lower()
    if key in index:
        return index[key]

    # 若傳入 Package.Node.SubNode，退化嘗試最後一段名稱
    if "." in key:
        tail = key.split(".")[-1]
        if tail in index:
            return index[tail]

    return None

def _search_addon_guid_entries(query: str, limit: int = 20) -> list:
    q = (query or "").strip().lower()
    if not q:
        return []

    entries = _load_addon_guid_mapping().get("entries", [])
    matches = []
    for e in entries:
        haystack = " ".join([
            str(e.get("package", "")),
            str(e.get("nodeDisplay", "")),
            str(e.get("guid", "")),
            str(e.get("note", "")),
        ]).lower()
        if q in haystack:
            matches.append(e)
            if len(matches) >= limit:
                break
    return matches

def _normalize_addon_guid_entry(entry: dict) -> dict:
    package = str(entry.get("package", "")).strip()
    node_display = str(entry.get("nodeDisplay", "")).strip()
    guid = str(entry.get("guid", "")).strip().lower()
    note = str(entry.get("note", "")).strip()
    source = str(entry.get("source", "")).strip()

    return {
        "package": package,
        "nodeDisplay": node_display,
        "guid": guid,
        "note": note,
        "source": source,
    }

def _merge_addon_guid_entries(existing: list[dict], incoming: list[dict]) -> list[dict]:
    merged = {}

    for entry in existing:
        normalized = _normalize_addon_guid_entry(entry)
        if normalized["guid"]:
            merged[normalized["guid"]] = normalized

    for entry in incoming:
        normalized = _normalize_addon_guid_entry(entry)
        if normalized["guid"]:
            merged[normalized["guid"]] = normalized

    return [merged[key] for key in sorted(merged.keys())]

def _write_addon_guid_mapping(entries: list[dict], source: str, output_path: str = ADDON_GUID_MAPPING_PATH) -> dict:
    payload = {
        "schemaVersion": "1.1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "entryCount": len(entries),
        "entries": entries,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    global _addon_guid_mapping
    _addon_guid_mapping = None
    _load_addon_guid_mapping()

    return payload

async def _collect_workspace_guid_candidates(session_id: str = None) -> list[dict]:
    """從當前工作區資源收集可疑外掛 GUID 候選。"""
    resource = await read_dynamo_resource(resourceType="nodes", sessionId=session_id)
    nodes = []

    if isinstance(resource, dict):
        nodes = resource.get("nodes", [])
        if not nodes and isinstance(resource.get("contents"), list):
            try:
                content_text = resource["contents"][0].get("text", "")
                parsed = json.loads(content_text)
                if isinstance(parsed, dict):
                    nodes = parsed.get("nodes", [])
            except Exception:
                nodes = []

    candidates = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        creation_name = str(node.get("creationName", "")).strip()
        full_name = str(node.get("fullName", "")).strip()
        display_name = str(node.get("name", "")).strip()

        if not creation_name or not _is_guid_like(creation_name):
            continue

        if not display_name:
            display_name = full_name.split(".")[-1] if full_name else creation_name

        package = ""
        if full_name and "." in full_name:
            package = full_name.split(".")[0]

        if package.startswith("Autodesk") or package.startswith("CoreNodeModels"):
            continue

        candidates.append({
            "package": package or "Unknown",
            "nodeDisplay": display_name,
            "guid": creation_name.lower(),
            "note": f"discovered from workspace node: {full_name or display_name}",
            "source": "workspace://current/nodes",
        })

    return candidates

def _collect_workspace_guid_candidates_from_snapshot(snapshot_path: str) -> list[dict]:
    """從離線快照檔案收集外掛 GUID 候選。"""
    if not snapshot_path:
        return []

    path = Path(snapshot_path)
    if not path.exists() or not path.is_file():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"[WARN] Failed to load snapshot {snapshot_path}: {e}")
        return []

    nodes = []
    if isinstance(data, dict):
        nodes = data.get("nodes", [])
        if not nodes and isinstance(data.get("contents"), list):
            try:
                content_text = data["contents"][0].get("text", "")
                parsed = json.loads(content_text)
                if isinstance(parsed, dict):
                    nodes = parsed.get("nodes", [])
            except Exception:
                nodes = []

    candidates = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        creation_name = str(node.get("creationName", "")).strip()
        full_name = str(node.get("fullName", "")).strip()
        display_name = str(node.get("name", "")).strip()

        if not creation_name or not _is_guid_like(creation_name):
            continue

        if not display_name:
            display_name = full_name.split(".")[-1] if full_name else creation_name

        package = ""
        if full_name and "." in full_name:
            package = full_name.split(".")[0]

        if package.startswith("Autodesk") or package.startswith("CoreNodeModels"):
            continue

        candidates.append({
            "package": package or "Unknown",
            "nodeDisplay": display_name,
            "guid": creation_name.lower(),
            "note": f"discovered from snapshot node: {full_name or display_name}",
            "source": str(path).replace("\\", "/"),
        })

    return candidates

# ==========================================
# MCP Resources Layer (dynamo:// URI Protocol)
# ==========================================

RESOURCE_TEMPLATES = [
    {
        "uriTemplate": "dynamo://workspace/current/nodes",
        "name": "All Nodes",
        "description": "取得當前工作區所有節點的結構化資料",
        "mimeType": "application/json"
    },
    {
        "uriTemplate": "dynamo://workspace/current/connectors",
        "name": "All Connectors",
        "description": "取得當前工作區所有連線的結構化資料",
        "mimeType": "application/json"
    },
    {
        "uriTemplate": "dynamo://workspace/selection",
        "name": "Selected Nodes",
        "description": "取得使用者目前選取的節點",
        "mimeType": "application/json"
    },
    {
        "uriTemplate": "dynamo://console/errors",
        "name": "Error Nodes",
        "description": "取得所有錯誤狀態節點與錯誤訊息",
        "mimeType": "application/json"
    },
    {
        "uriTemplate": "dynamo://node/{nodeId}",
        "name": "Node Details",
        "description": "取得指定節點的完整資訊（包含輸入輸出值）",
        "mimeType": "application/json"
    }
]

async def _list_resources() -> dict:
    """返回可用資源模板列表 (MCP resources/list)"""
    return {"resourceTemplates": RESOURCE_TEMPLATES}

async def _read_resource(uri: str, session_id: str = None) -> dict:
    """讀取指定 URI 的資源內容 (MCP resources/read)"""
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
    if not sessions:
        return {"error": "No active Dynamo connections"}
    
    target_id = session_id if session_id and session_id in sessions else sessions[-1]
    
    # 解析 URI 並路由至對應 C# 端 action
    action_map = {
        "dynamo://workspace/current/nodes": {"action": "get_nodes_structured"},
        "dynamo://workspace/current/connectors": {"action": "get_connectors_structured"},
        "dynamo://workspace/selection": {"action": "get_selection"},
        "dynamo://console/errors": {"action": "get_error_nodes"}
    }
    
    if uri in action_map:
        cmd = action_map[uri]
    elif uri.startswith("dynamo://node/"):
        node_id = uri.replace("dynamo://node/", "")
        cmd = {"action": "get_node_details", "nodeId": node_id}
    else:
        return {"error": f"Unknown resource URI: {uri}"}
    
    try:
        result = await ws_manager.send_command_async(target_id, cmd)
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(result, ensure_ascii=False)}]}
    except Exception as e:
        return {"error": str(e)}

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

    async def run(self, host="127.0.0.1", port=65535):
        self.host = host
        self.port = port
        log(f"[Dynamo-WS] Listener starting on ws://{host}:{port}")
        async with websockets.serve(self._handle_connection, self.host, self.port):
            await asyncio.Future()  # Run forever

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

    async def cleanup_stale_sessions(self, timeout=300.0):
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
    
    def __init__(self, host="127.0.0.1", port=65296):
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
                    elif method == "resources/list":
                        result = await _list_resources()
                    elif method == "resources/read":
                        uri = params.get("uri", "")
                        session_id = params.get("sessionId")
                        result = await _read_resource(uri, session_id)
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
                "description": "在 Dynamo 中執行節點創建指令。支援 dryRun 模式預覽、clientId 識別客戶端、expectedVersion 避免多客戶端衝突。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "instructions": {
                            "type": "string",
                            "description": "JSON 格式的完整圖形定義。必須包含 'nodes' 和 'connectors'。Python 節點需指定 'pythonCode' 欄位。"
                        },
                        "dryRun": {
                            "type": "boolean",
                            "description": "若為 true，僅回傳預覽報告（包含節點清單、連線、潛在警告）而不實際執行。預設為 false。"
                        },
                        "clientId": {
                            "type": "string",
                            "description": "客戶端識別碼（如 'antigravity', 'gemini-cli', 'claude'）。用於追蹤誰執行了修改。"
                        },
                        "expectedVersion": {
                            "type": "integer",
                            "description": "預期的工作區版本號。若不匹配則拒絕執行並回傳 version_conflict。透過 get_workspace_version 取得當前版本。"
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
                "name": "run_autotest",
                "description": "執行專案自動化測試 (test_roadmap_features.py)。驗證 Dynamo 節點放置、Python 注入、外掛支援與幾何運算功能。",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                },
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
            {
                "name": "generate_workspace_mermaid",
                "description": "分析當前 Dynamo 工作區邏輯，輸出 Mermaid 流程圖、邏輯摘要與 Markdown 報告。支援離線 snapshot 驗證。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定要分析的 Session ID。"
                        },
                        "snapshotPath": {
                            "type": "string",
                            "description": "選用。離線工作區快照 JSON 路徑；提供後會優先分析快照而非即時連線。"
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["LR", "TD", "RL", "BT"],
                            "description": "Mermaid 圖表方向，預設 LR。"
                        },
                        "maxNodes": {
                            "type": "integer",
                            "description": "Mermaid 最多保留的節點數；大型圖表會自動摘要，預設 60。"
                        },
                        "saveToFile": {
                            "type": "boolean",
                            "description": "是否將 Markdown 報告寫入 image/ 或 outputPath。預設 false。"
                        },
                        "outputPath": {
                            "type": "string",
                            "description": "選用。若 saveToFile=true，可指定輸出檔案完整路徑。"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["pipeline", "semantic", "detail"],
                            "description": "圖表模式。pipeline（預設）：工作流階段觀，最可讀；semantic：同名節點合併；detail：1:1 節點對應（debug 用）。"
                        }
                    }
                },
                "readOnlyHint": False
            },
            {
                "name": "create_group",
                "description": "將節點群組化 (Group Nodes)。能夠為指定的節點創建一個帶標題和描述的群組。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "nodeIds": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要分組的節點 ID 清單"
                        },
                        "title": {
                            "type": "string",
                            "description": "群組標題",
                            "default": "New Group"
                        },
                        "description": {
                            "type": "string",
                            "description": "群組描述",
                            "default": ""
                        },
                        "color": {
                            "type": "string",
                            "description": "群組顏色 (Hex)",
                            "default": "#FFC1D5E0"
                        },
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定要執行的 Session ID"
                        },
                        "validateNodeIds": {
                            "type": "boolean",
                            "description": "是否先驗證 nodeIds 是否存在於工作區，預設 true",
                            "default": True
                        },
                        "retryCount": {
                            "type": "integer",
                            "description": "失敗時重試次數，預設 2",
                            "default": 2
                        }
                    },
                    "required": ["nodeIds"]
                },
                "destructiveHint": True
            },
            {
                "name": "auto_group",
                "description": "智慧自動分組 (Auto Group)。自動分析工作區節點，依功能分成輸入/運算/輸出三組並建立色彩群組。支援自訂顏色、描述文字與分組方式。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["auto", "custom"],
                            "description": "分組模式：auto=自動依節點類型分類（預設）；custom=手動指定各群組節點",
                            "default": "auto"
                        },
                        "input_title": {"type": "string", "description": "輸入群組標題", "default": "輸入參數"},
                        "input_desc": {"type": "string", "description": "輸入群組說明文字", "default": "使用者可調整的輸入參數，控制腳本行為"},
                        "input_color": {"type": "string", "description": "輸入群組顏色 (Hex ARGB)", "default": "#FFE91E8A"},
                        "compute_title": {"type": "string", "description": "運算群組標題", "default": "核心運算"},
                        "compute_desc": {"type": "string", "description": "運算群組說明文字", "default": "資料處理與幾何運算邏輯"},
                        "compute_color": {"type": "string", "description": "運算群組顏色 (Hex ARGB)", "default": "#FF4169E1"},
                        "output_title": {"type": "string", "description": "輸出群組標題", "default": "結果輸出"},
                        "output_desc": {"type": "string", "description": "輸出群組說明文字", "default": "觀察與驗證運算結果"},
                        "output_color": {"type": "string", "description": "輸出群組顏色 (Hex ARGB)", "default": "#FF228B22"},
                        "groups": {
                            "type": "array",
                            "description": "[custom 模式] 自訂群組清單",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "color": {"type": "string"},
                                    "nodeIds": {"type": "array", "items": {"type": "string"}}
                                }
                            }
                        }
                    }
                },
                "destructiveHint": True
            },
            # === 通用工具橋接層 (Universal Tool Bridge) ===
            {
                "name": "read_dynamo_resource",
                "description": "讀取 Dynamo 工作區資源。適用於不支援 MCP resources/read 的客戶端（如 Gemini CLI、Cursor）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "resourceType": {
                            "type": "string",
                            "enum": ["nodes", "connectors", "selection", "errors"],
                            "description": "資源類型：nodes=所有節點, connectors=所有連線, selection=選取的節點, errors=錯誤節點"
                        },
                        "nodeId": {
                            "type": "string",
                            "description": "選用。取得單一節點詳情時使用（需配合 resourceType='nodes'）"
                        },
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定 Session ID"
                        }
                    },
                    "required": ["resourceType"]
                },
                "readOnlyHint": True
            },
            {
                "name": "get_workspace_version",
                "description": "取得當前工作區的版本號與最後寫入者資訊。用於實作樂觀鎖，避免多客戶端衝突。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定 Session ID"
                        }
                    }
                },
                "readOnlyHint": True
            },
            # === Memory Bank 快取管理 ===
            {
                "name": "get_memory_bank_summary",
                "description": "取得 Memory Bank 快取摘要（系統模式、已知坑、近期決策、教訓庫）。**建議每次新對話開始時先呼叫**，避免重複踩坑。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "enum": ["all", "activeContext", "lessons", "systemPatterns", "progress"],
                            "description": "選用。指定要取得的區段：all=完整摘要（預設）, activeContext=當前狀態, lessons=教訓庫, systemPatterns=系統模式, progress=進度追蹤"
                        }
                    }
                },
                "readOnlyHint": True
            },
            {
                "name": "reload_memory_bank",
                "description": "手動重新載入 Memory Bank（當 memory-bank/ 資料夾內容有更新時使用）。",
                "inputSchema": {"type": "object", "properties": {}},
                "readOnlyHint": True
            },
            {
                "name": "refresh_addon_guid_mapping",
                "description": "從當前工作區節點資源與既有知識庫更新外掛 GUID 映射表。可用於自動擴充 domain/addon_guid_mapping.json。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sessionId": {
                            "type": "string",
                            "description": "選用。指定要掃描的 Session ID"
                        },
                        "snapshotPath": {
                            "type": "string",
                            "description": "選用。離線快照檔案路徑；若提供則優先從快照讀取 nodes。"
                        },
                        "includeKnown": {
                            "type": "boolean",
                            "description": "是否保留並重新寫入既有映射資料，預設為 true",
                            "default": True
                        }
                    }
                },
                "readOnlyHint": False
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
            elif name == "run_autotest":
                return await run_autotest_async()
            elif name == "list_sessions":
                return await list_sessions()
            elif name == "get_server_stats":
                return get_server_stats()
            elif name == "generate_workspace_mermaid":
                return await generate_workspace_mermaid(**args)
            elif name == "read_dynamo_resource":
                return await read_dynamo_resource(**args)
            elif name == "get_workspace_version":
                return await get_workspace_version(**args)
            elif name == "get_memory_bank_summary":
                return get_memory_bank_summary(**args)
            elif name == "reload_memory_bank":
                return reload_memory_bank()
            elif name == "refresh_addon_guid_mapping":
                return await refresh_addon_guid_mapping(**args)
            elif name == "create_group":
                return await create_group(**args)
            elif name == "auto_group":
                return await auto_group(**args)
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

async def read_dynamo_resource(resourceType: str, nodeId: str = None, sessionId: str = None) -> dict:
    """
    通用工具橋接：將 Resources 層包裝成標準工具
    適用於不支援 MCP resources/read 的客戶端
    """
    uri_map = {
        "nodes": "dynamo://workspace/current/nodes",
        "connectors": "dynamo://workspace/current/connectors",
        "selection": "dynamo://workspace/selection",
        "errors": "dynamo://console/errors"
    }
    
    if nodeId:
        uri = f"dynamo://node/{nodeId}"
    elif resourceType in uri_map:
        uri = uri_map[resourceType]
    else:
        return {"error": f"Unknown resourceType: {resourceType}. Valid: nodes, connectors, selection, errors"}
    
    # 透過內部 _read_resource 取得資料
    result = await _read_resource(uri, sessionId)
    
    # 取得版本資訊
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
    
    if sessions:
        target_session = sessionId if sessionId in sessions else sessions[-1]
        state = session_state_manager.get_state(target_session)
        version_info = state.get_info()
    else:
        version_info = {"version": 0, "sessionId": None}
    
    # 合併回傳
    if "error" in result:
        return result
    
    if "contents" in result:
        try:
            content = json.loads(result["contents"][0]["text"])
            content["_version"] = version_info["version"]
            content["_sessionId"] = version_info["sessionId"]
            return content
        except:
            return result
    
    return result

async def get_workspace_version(sessionId: str = None) -> dict:
    """
    取得工作區版本資訊
    用於實作樂觀鎖，避免多客戶端衝突
    """
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
    
    if not sessions:
        return {"error": "No active Dynamo connections"}
    
    target_session = sessionId if sessionId in sessions else sessions[-1]
    state = session_state_manager.get_state(target_session)
    
    return {
        "status": "ok",
        **state.get_info()
    }


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

def _detect_potential_issues(nodes: list, connectors: list) -> list:
    """偵測潛在問題 (Human-in-the-Loop)"""
    warnings = []
    
    # 檢查節點位置重疊
    positions = {}
    for n in nodes:
        pos = (n.get("x", 0), n.get("y", 0))
        if pos in positions:
            warnings.append(f"警告: 節點 '{n.get('id')}' 與 '{positions[pos]}' 位置重疊")
        positions[pos] = n.get("id")
    
    # 檢查未連接的節點
    connected_ids = set()
    for c in connectors:
        connected_ids.add(c.get("from"))
        connected_ids.add(c.get("to"))
    
    for n in nodes:
        if n.get("id") not in connected_ids and n.get("name") != "Number" and n.get("name") != "Code Block":
            warnings.append(f"注意: 節點 '{n.get('id')}' 未連接任何其他節點")
    
    return warnings

def _generate_dry_run_report(json_data: dict, base_x: float, base_y: float) -> dict:
    """
    生成預覽報告，包含：
    1. 將創建的節點清單
    2. 將建立的連線清單
    3. 潛在風險警告
    4. 預估畫布佔用範圍
    """
    expanded = _expand_native_nodes(json_data)
    
    nodes = expanded.get("nodes", [])
    connectors = expanded.get("connectors", [])
    
    # 套用座標偏移
    for node in nodes:
        node["x"] = float(node.get("x", 0)) + base_x
        node["y"] = float(node.get("y", 0)) + base_y
    
    # 計算佔用範圍
    xs = [n.get("x", 0) for n in nodes]
    ys = [n.get("y", 0) for n in nodes]
    
    report = {
        "status": "dry_run",
        "summary": {
            "nodesToCreate": len(nodes),
            "connectorsToCreate": len(connectors),
            "estimatedBounds": {
                "minX": min(xs) if xs else 0,
                "maxX": max(xs) if xs else 0,
                "minY": min(ys) if ys else 0,
                "maxY": max(ys) if ys else 0
            }
        },
        "nodes": [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "position": {"x": n.get("x", 0), "y": n.get("y", 0)}
            }
            for n in nodes
        ],
        "connectors": connectors,
        "warnings": _detect_potential_issues(nodes, connectors)
    }
    
    return report

async def execute_dynamo_instructions(
    instructions: str, 
    clear_before_execute: bool = False, 
    base_x: float = 0, 
    base_y: float = 0, 
    allow_fallback: bool = True, 
    sessionId: str = None, 
    dryRun: bool = False,
    clientId: str = "anonymous",      # 多客戶端支援：客戶端識別
    expectedVersion: int = None       # 多客戶端支援：預期版本號
) -> str:
    """
    執行 Dynamo 節點創建指令
    
    多客戶端衝突避免機制：
    - clientId: 識別發送指令的客戶端
    - expectedVersion: 預期的工作區版本號，若不匹配則拒絕執行
    """
    # Human-in-the-Loop: Dry Run 模式
    try:
        json_data = json.loads(instructions)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"JSON 解析錯誤: {str(e)}"}, ensure_ascii=False)
    
    if isinstance(json_data, list):
        json_data = {"nodes": json_data, "connectors": []}
    
    if dryRun:
        report = _generate_dry_run_report(json_data, base_x, base_y)
        return json.dumps(report, ensure_ascii=False, indent=2)
    
    with ws_manager._lock: sessions = list(ws_manager.active_sessions.keys())
    if not sessions: return json.dumps({"status": "error", "message": "未連線"}, ensure_ascii=False)
    
    if sessionId and sessionId not in sessions:
        return json.dumps({"status": "error", "message": f"找不到指定的會話 {sessionId}"}, ensure_ascii=False)
    
    session_id = sessionId if sessionId else sessions[-1]
    
    # === 樂觀鎖：版本控制 ===
    state = session_state_manager.get_state(session_id)
    success, version_result = await state.acquire_write(clientId, expectedVersion)
    
    if not success:
        # 版本衝突，拒絕執行
        return json.dumps(version_result, ensure_ascii=False)
    
    new_version = version_result["newVersion"]
    
    mapped_nodes = []

    try:
        # 座標偏移與策略標註
        if "nodes" in json_data:
            for node in json_data["nodes"]:
                original_name = node.get("name", "")

                # 外掛節點映射：若提供的是名稱別名，優先解析為 GUID
                mapped = _resolve_addon_guid(original_name)
                if mapped:
                    node["name"] = mapped["guid"]
                    mapped_nodes.append({
                        "id": node.get("id", ""),
                        "from": original_name,
                        "to": mapped["guid"],
                        "package": mapped.get("package", ""),
                        "nodeDisplay": mapped.get("nodeDisplay", "")
                    })

                route_node_creation(node)
                node["x"] = float(node.get("x", 0)) + base_x
                node["y"] = float(node.get("y", 0)) + base_y
        
        if clear_before_execute: 
            await ws_manager.send_command_async(session_id, {"action": "clear_graph"})
        
        # 首次嘗試執行
        response = await ws_manager.send_command_async(session_id, json_data)
        
        # [核心優化] 差異化重試與降級機制 (Differentiated Fallback)
        if response.get("status") == "error" and allow_fallback:
            log(f"[Fallback] 軌道 B 執行失敗，嘗試降級至軌道 A (Code Block)... 錯誤: {response.get('message')}")
            
            # [修正] 根據使用者要求，禁止自動清空工作區 (User Rule: 不允許自動清空工作區)
            # log("[Fallback] 清除失敗節點...")
            # await ws_manager.send_command_async(session_id, {"action": "clear_graph"})
            
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
                return json.dumps({
                    "status": "ok",
                    "message": "成功 (已透過軌道 A 降級重試恢復)",
                    "version": new_version,
                    "clientId": clientId,
                    "mappedNodes": mapped_nodes
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"失敗 (重試後仍錯誤): {retry_response.get('message')}",
                    "version": new_version,
                    "mappedNodes": mapped_nodes
                }, ensure_ascii=False)
        
        if response.get("status") == "ok":
            return json.dumps({
                "status": "ok",
                "message": "成功",
                "version": new_version,
                "clientId": clientId,
                "sessionId": session_id,
                "mappedNodes": mapped_nodes
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "error",
                "message": response.get('message'),
                "version": new_version,
                "mappedNodes": mapped_nodes
            }, ensure_ascii=False)
    except Exception as e: 
        return json.dumps({"status": "error", "message": str(e), "version": new_version, "mappedNodes": mapped_nodes}, ensure_ascii=False)

async def search_nodes_async(query: str) -> str:
    with ws_manager._lock: sessions = list(ws_manager.active_sessions.keys())

    # 沒有 Dynamo 連線時，仍可使用本地 addon GUID 映射做離線查詢
    if not sessions:
        addon_hits = _search_addon_guid_entries(query)
        if not addon_hits:
            return "[FAIL] 失敗: 未連線"

        res = [f"[SEARCH] 離線映射搜尋 '{query}' 找到 {len(addon_hits)} 個結果：\n"]
        for n in addon_hits:
            res.append(f"- **{n.get('package', '')}.{n.get('nodeDisplay', '')}**")
            res.append(f"  guid: `{n.get('guid', '')}`")
            if n.get("note"): res.append(f"  備註: {n.get('note')}")
            res.append("")
        return "\n".join(res)

    session_id = sessions[-1]
    try:
        data = await ws_manager.send_command_async(session_id, {"action": "list_nodes", "filter": query})
        if data.get("status") == "error": return f"[FAIL] 搜尋出錯: {data.get('message')}"
        
        # If the backend provided a formatted display string, use it
        if data.get("display"):
            return data["display"]

        nodes = data.get("nodes", [])
        if not nodes: return f"[SEARCH] 搜尋 '{query}': 找不到任何節點。"
        
        # Fallback formatting
        res = [f"[SEARCH] 搜尋 '{query}' 找到 {data.get('count', 0)} 個結果 (僅列出前 50 個):\n"]
        for n in nodes:
            res.append(f"- **{n['name']}**")
            res.append(f"  fullName: `{n['fullName']}`")
            if n.get('creationName'): res.append(f"  creationName: `{n['creationName']}`")
            if n.get('description'): res.append(f"  說明: {n['description']}")
            res.append("")

        addon_hits = _search_addon_guid_entries(query)
        if addon_hits:
            res.append("[Addon GUID 映射結果]")
            for n in addon_hits:
                res.append(f"- **{n.get('package', '')}.{n.get('nodeDisplay', '')}**")
                res.append(f"  guid: `{n.get('guid', '')}`")
                if n.get("note"): res.append(f"  備註: {n.get('note')}")
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
        return f"[FAIL] 失敗: {res}"
    
    # [核心優化] 幽靈連線偵測與詳細狀態
    if session_count > 1:
        data = json.loads(res)
        data["warning"] = f"[WARNING] 警告: 偵測到 {session_count} 個活動中的會話。指令目前預設發送至最後一個連線 (Session: {sessions[-1]})。若不正確，請使用 list_sessions 查看並指定 sessionId。"
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
    
    if not sessions: return "[NO SESSIONS] 目前沒有活動中的會話。"
    
    lines = ["[SESSIONS] 活動中的 Dynamo 會話清單：\n"]
    for i, (sid, info) in enumerate(sessions.items()):
        status = "[ACTIVE]" if (time.time() - info["lastSeen"]) < 10 else "[IDLE]"
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
    if not sessions: return "[FAIL] 失敗"
    res = await ws_manager.send_command_async(sessions[-1], {"action": "clear_graph"})
    return "[OK] 已清空" if res.get("status") == "ok" else f"[FAIL] 失敗"

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

async def run_autotest_async() -> dict:
    """執行自動化測試腳本"""
    import subprocess
    import sys
    
    from pathlib import Path
    
    # 修正: 使用 Path(__file__) 定位，不依賴未定義的 BASE_DIR
    current_dir = Path(__file__).parent.resolve()
    # server.py 在 bridge/python/server.py，專案根目錄在 ../../
    project_root = current_dir.parent.parent
    script_path = project_root / "tools" / "autotest.py"
    
    if not script_path.exists():
        return {"error": f"Test script not found at {script_path}"}
        
    try:
        # 強制設定 UTF-8 環境變數
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"

        # 使用目前的 python 解譯器執行
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            env=env  # 注入環境變數
        )
        
        status = "passed" if result.returncode == 0 else "failed"
        
        return {
            "status": status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except Exception as e:
        return {"error": f"Failed to run autotest: {str(e)}"}

def get_memory_bank_summary(section: str = "all") -> str:
    """
    取得 Memory Bank 快取摘要
    Args:
        section: 指定區段 (all, activeContext, lessons, systemPatterns, progress)
    Returns:
        格式化的摘要內容
    """
    if MEMORY_BANK_SUMMARY is None:
        return json.dumps({"error": "Memory Bank 尚未載入。請重啟 Server 或呼叫 reload_memory_bank。"}, ensure_ascii=False)
    
    if MEMORY_BANK_SUMMARY.get("status") == "error":
        return json.dumps(MEMORY_BANK_SUMMARY, ensure_ascii=False)
    
    try:
        if section == "activeContext":
            content = MEMORY_BANK_SUMMARY.get("activeContext", "(無內容)")
            return f"# 當前工作焦點\n\n{content}"
        
        elif section == "lessons":
            lessons = MEMORY_BANK_SUMMARY.get("lessons", [])
            if not lessons:
                return "# 教訓庫\n\n(無已記錄教訓)"
            
            lines = ["# 教訓庫摘要\n"]
            for i, lesson in enumerate(lessons, 1):
                lines.append(f"## {i}. {lesson['title']} ({lesson['file']})")
                lines.append(f"{lesson['summary'][:300]}...\n")
            return "\n".join(lines)
        
        elif section == "systemPatterns":
            content = MEMORY_BANK_SUMMARY.get("systemPatterns", "(無內容)")
            return f"# 系統架構與設計模式\n\n{content[:1500]}...\n\n(完整內容請參考 memory-bank/systemPatterns.md)"
        
        elif section == "progress":
            content = MEMORY_BANK_SUMMARY.get("progress", "(無內容)")
            return f"# 專案進度追蹤\n\n{content[:1000]}...\n\n(完整內容請參考 memory-bank/progress.md)"
        
        else:  # section == "all"
            lessons = MEMORY_BANK_SUMMARY.get("lessons", [])
            active = MEMORY_BANK_SUMMARY.get("activeContext", "")
            
            summary_text = f"""# Memory Bank 摘要
> 載入時間：{MEMORY_BANK_LOAD_TIME}
> 教訓數量：{len(lessons)}

## 📍 當前工作焦點
{active[:800]}...

## 🧠 系統模式 (SSOT)
{MEMORY_BANK_SUMMARY.get('systemPatterns', '')[:600]}...

## 📊 專案進度
{MEMORY_BANK_SUMMARY.get('progress', '')[:500]}...

## 📚 核心教訓（前 5 條）
"""
            
            for i, lesson in enumerate(lessons[:5], 1):
                summary_text += f"\n### {i}. {lesson['title']}\n{lesson['summary'][:200]}...\n"
            
            if len(lessons) > 5:
                summary_text += f"\n... 還有 {len(lessons) - 5} 條教訓，使用 section='lessons' 查看完整列表\n"
            
            summary_text += "\n\n---\n**使用建議**: 每次新對話開始時呼叫此工具，避免重複踩坑。\n"
            
            return summary_text
    
    except Exception as e:
        return json.dumps({"error": f"Failed to format summary: {e}"}, ensure_ascii=False)

def reload_memory_bank() -> str:
    """
    手動重新載入 Memory Bank
    Returns:
        載入狀態
    """
    result = load_memory_bank()
    
    if result.get("status") == "ok":
        return json.dumps({
            "status": "ok",
            "message": "✅ Memory Bank 已重新載入",
            "loadTime": result["loadTime"],
            "lessonsCount": result["lessonsCount"]
        }, ensure_ascii=False, indent=2)
    else:
        return json.dumps(result, ensure_ascii=False, indent=2)

async def refresh_addon_guid_mapping(sessionId: str = None, snapshotPath: str = None, includeKnown: bool = True) -> dict:
    """根據目前工作區資料自動擴充外掛 GUID 映射表。"""
    existing_entries = []
    source_note = "workspace://current/nodes"

    if includeKnown and os.path.exists(ADDON_GUID_MAPPING_PATH):
        try:
            with open(ADDON_GUID_MAPPING_PATH, "r", encoding="utf-8") as f:
                existing_payload = json.load(f)
            existing_entries = existing_payload.get("entries", []) if isinstance(existing_payload, dict) else []
        except Exception as e:
            log(f"[WARN] Failed to load existing addon mapping: {e}")

    try:
        if snapshotPath:
            workspace_candidates = _collect_workspace_guid_candidates_from_snapshot(snapshotPath)
            source_note = snapshotPath
        else:
            workspace_candidates = await _collect_workspace_guid_candidates(session_id=sessionId)

        merged_entries = _merge_addon_guid_entries(existing_entries, workspace_candidates)

        added_guids = {entry["guid"] for entry in workspace_candidates}
        existing_guids = {str(entry.get("guid", "")).strip().lower() for entry in existing_entries if str(entry.get("guid", "")).strip()}
        new_count = len([guid for guid in added_guids if guid not in existing_guids])

        payload = _write_addon_guid_mapping(
            merged_entries,
            source=f"workspace refresh ({source_note}) + {ADDON_GUID_MAPPING_PATH}",
        )

        return {
            "status": "ok",
            "entryCount": payload["entryCount"],
            "addedCount": len(added_guids),
            "newCount": new_count,
            "source": source_note,
            "mappingPath": ADDON_GUID_MAPPING_PATH,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "mappingPath": ADDON_GUID_MAPPING_PATH,
        }

def _deduplicate_ids(ids: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for item in ids:
        sid = str(item).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        ordered.append(sid)
    return ordered

async def _get_workspace_node_ids(session_id: str = None) -> set:
    try:
        resource = await read_dynamo_resource(resourceType="nodes", sessionId=session_id)
    except Exception:
        return set()

    nodes = []
    if isinstance(resource, dict):
        nodes = resource.get("nodes", [])
        if not nodes and isinstance(resource.get("contents"), list):
            try:
                content_text = resource["contents"][0].get("text", "")
                parsed = json.loads(content_text)
                if isinstance(parsed, dict):
                    nodes = parsed.get("nodes", [])
            except Exception:
                nodes = []

    return {str(n.get("id", "")).strip() for n in nodes if isinstance(n, dict) and n.get("id")}

async def create_group(
    nodeIds: List[str],
    title: str = "New Group",
    description: str = "",
    color: str = "#FFC1D5E0",
    sessionId: str = None,
    validateNodeIds: bool = True,
    retryCount: int = 2,
) -> dict:
    """
    建立節點群組
    """
    if not isinstance(nodeIds, list) or not nodeIds:
        return {"status": "error", "message": "nodeIds 必須是非空陣列"}

    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())
    
    if not sessions:
        return {"error": "No active Dynamo connections"}
    
    if sessionId and sessionId not in sessions:
        return {"status": "error", "message": f"找不到指定會話 {sessionId}"}

    session_id = sessionId if sessionId else sessions[-1]
    deduped_ids = _deduplicate_ids(nodeIds)
    if not deduped_ids:
        return {"status": "error", "message": "nodeIds 去重後為空"}

    missing_ids = []
    valid_ids = deduped_ids

    if validateNodeIds:
        workspace_ids = await _get_workspace_node_ids(session_id=session_id)
        if workspace_ids:
            valid_ids = [nid for nid in deduped_ids if nid in workspace_ids]
            missing_ids = [nid for nid in deduped_ids if nid not in workspace_ids]

    if not valid_ids:
        return {
            "status": "error",
            "message": "沒有可分組的有效節點 ID",
            "requestedCount": len(nodeIds),
            "dedupedCount": len(deduped_ids),
            "validCount": 0,
            "missingNodeIds": missing_ids,
        }
    
    cmd = {
        "action": "create_group",
        "nodeIds": valid_ids,
        "title": title,
        "description": description,
        "color": color
    }
    
    safe_retry_count = max(0, min(int(retryCount), 5))
    last_error = None
    for attempt in range(safe_retry_count + 1):
        try:
            result = await ws_manager.send_command_async(session_id, cmd)
            if result.get("status") == "ok":
                enriched = {
                    **result,
                    "requestedCount": len(nodeIds),
                    "dedupedCount": len(deduped_ids),
                    "validCount": len(valid_ids),
                    "missingNodeIds": missing_ids,
                    "sessionId": session_id,
                    "attempt": attempt + 1,
                }
                if missing_ids:
                    enriched["warning"] = f"略過 {len(missing_ids)} 個不存在於工作區的節點"
                return enriched

            last_error = result.get("message", "unknown error")
        except Exception as e:
            last_error = str(e)

        if attempt < safe_retry_count:
            await asyncio.sleep(0.15 * (attempt + 1))

    return {
        "status": "error",
        "message": last_error or "create_group failed",
        "requestedCount": len(nodeIds),
        "dedupedCount": len(deduped_ids),
        "validCount": len(valid_ids),
        "missingNodeIds": missing_ids,
        "sessionId": session_id,
        "attempts": safe_retry_count + 1,
    }


# 輸入節點的 fullName 前綴清單
_INPUT_PREFIXES = (
    "CoreNodeModels.Input.",      # Number, Slider, String, Bool, File...
    "DSCore.Input.",
)
# 輸出節點的 name 清單
_OUTPUT_NAMES = {"Watch", "Watch 3D", "Python Script"}
_OUTPUT_FULL = ("CoreNodeModels.Watch",)

# ---- Pipeline stage 分類規則 (優先序由高到低) ----
# 每個 tuple: (stage_key, [pattern_substrings...]) — 全小寫比對
_PIPELINE_STAGES: list[tuple[str, list[str]]] = [
    ("observation",       ["watch 3d", "watch", "python script", "python"]),
    ("output_geometry",   ["extrude", "form.", "importinstance", "directshape", "familyinstance", "floor.", "wall.", "roof."]),
    ("surface_analysis",  ["polysurface", "surface.area", "surface.perimeter", "surface.pointat", "surface.normal", "surface.offset"]),
    ("surface_ops",       ["surface.byloft", "surface.bysweep", "surface.byruled", "surface.bypath", "nurbssurface.", "surface.byplane", "surface.bytrim"]),
    ("solid_ops",         ["solid.", "sphere.", "cylinder.", "cuboid.", "cone."]),
    ("data_assembly",     ["list.", "dictionary.", "sequence.", "createlist", "flattenlist", "transpose"]),
    ("curve_ops",         ["line.", "arc.", "circle.", "ellipse.", "nurbscurve.", "curve.by", "polycurve.", "helix."]),
    ("point_ops",         ["point.by", "point.origin", "vector.", "plane.", "coordinatesystem.", "uv."]),
    ("revit_model",       ["element.", "room.", "door.", "window.", "column.", "beam.", "filteredel", "collector"]),
    ("input",             ["number", "slider", "code block", "select", "boolean", "string", "integer", "double", "filepath", "filename"]),
]

_STAGE_LABELS_ZH: dict[str, str] = {
    "input":           "輸入參數",
    "revit_model":     "Revit 模型",
    "point_ops":       "幾何建構",
    "curve_ops":       "曲線生成",
    "data_assembly":   "清單彙整",
    "solid_ops":       "實體運算",
    "surface_ops":     "曲面運算",
    "surface_analysis":"後處理",
    "output_geometry": "輸出幾何",
    "observation":     "觀察輸出",
}

def _assign_pipeline_stage(node: dict) -> str:
    """依節點顯示名稱/fullName 判斷其所屬的 Pipeline 階段 key。"""
    name = str(node.get("name") or "").lower().strip()
    full = str(node.get("fullName") or "").lower().strip()
    combined = f"{name} {full}"
    for stage_key, patterns in _PIPELINE_STAGES:
        if any(p in combined for p in patterns):
            return stage_key
    # fallback: 沿用 category
    cat = node.get("category", "compute")
    return "input" if cat == "input" else ("observation" if cat == "output" else "surface_ops")


async def auto_group(
    mode: str = "auto",
    input_title: str = "輸入參數",
    input_desc: str = "使用者可調整的輸入參數，控制腳本行為",
    input_color: str = "#FFE91E8A",
    compute_title: str = "核心運算",
    compute_desc: str = "資料處理與幾何運算邏輯",
    compute_color: str = "#FF4169E1",
    output_title: str = "結果輸出",
    output_desc: str = "觀察與驗證運算結果",
    output_color: str = "#FF228B22",
    groups: list = None
) -> dict:
    """
    智慧分組工具：自動分析工作區並建立輸入/運算/輸出三組
    """
    with ws_manager._lock:
        sessions = list(ws_manager.active_sessions.keys())

    if not sessions:
        return {"error": "No active Dynamo connections"}

    session_id = sessions[-1]

    # === custom 模式：直接使用使用者提供的分組清單 ===
    if mode == "custom" and groups:
        results = []
        for g in groups:
            r = await create_group(
                nodeIds=g.get("nodeIds", []),
                title=g.get("title", "Group"),
                description=g.get("description", ""),
                color=g.get("color", "#FFC1D5E0")
            )
            results.append({"title": g.get("title"), "result": r})
        created = sum(1 for r in results if r["result"].get("status") == "ok")
        return {"status": "ok", "groups_created": created, "details": results}

    # === auto 模式：分析工作區並分類節點 ===
    try:
        raw = await analyze_workspace()
    except Exception as e:
        return {"error": f"Failed to analyze workspace: {e}"}

    if isinstance(raw, str):
        if raw.startswith("[FAIL]"):
            return {"error": raw}
        ws_data = json.loads(raw)
    else:
        ws_data = raw

    nodes = ws_data.get("nodes", [])
    if not nodes:
        return {"error": "No nodes found in workspace"}


    input_ids, compute_ids, output_ids = [], [], []

    for node in nodes:
        nid = node.get("id", "")
        full_name = node.get("fullName", "")
        name = node.get("name", "")

        # 判斷輸出節點
        is_output = (
            any(full_name.startswith(p) for p in _OUTPUT_FULL)
            or name in _OUTPUT_NAMES
        )
        # 判斷輸入節點
        is_input = any(full_name.startswith(p) for p in _INPUT_PREFIXES)

        if is_output:
            output_ids.append(nid)
        elif is_input:
            input_ids.append(nid)
        else:
            compute_ids.append(nid)

    log(f"[auto_group] Input={len(input_ids)}, Compute={len(compute_ids)}, Output={len(output_ids)}")

    results = []
    group_defs = [
        (input_ids,   input_title,   input_desc,   input_color),
        (compute_ids, compute_title, compute_desc, compute_color),
        (output_ids,  output_title,  output_desc,  output_color),
    ]

    for node_ids, title, desc, color in group_defs:
        if not node_ids:
            results.append({"title": title, "result": {"status": "skipped", "reason": "no nodes"}})
            continue
        r = await create_group(nodeIds=node_ids, title=title, description=desc, color=color)
        results.append({"title": title, "node_count": len(node_ids), "result": r})

    created = sum(1 for r in results if r["result"].get("status") == "ok")
    return {
        "status": "ok",
        "mode": "auto",
        "groups_created": created,
        "breakdown": {
            "input": len(input_ids),
            "compute": len(compute_ids),
            "output": len(output_ids)
        },
        "details": results
    }

# ==========================================
# 入口點
# ==========================================

if __name__ == "__main__":
    log("==========================================")
    log("  Dynamo WebSocket Manager (Python)")
    log("==========================================")
    log("")
    
    # 取得設定的連接埠
    dynamo_port = CONFIG.get("server", {}).get("websocket_port", 65535)
    bridge_port = 65296
    
    bridge_server = MCPBridgeServer(port=bridge_port)
    
    async def main():
        # 啟動時載入 Memory Bank
        load_memory_bank()
        
        # 同時啟動兩個非同步服務，共用同一個 Event Loop
        await asyncio.gather(
            ws_manager.run("127.0.0.1", dynamo_port),
            bridge_server.serve()
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("\nServer stopped by user.")
    except Exception as e:
        log(f"\nServer Fatal Error: {e}")
