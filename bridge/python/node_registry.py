"""
Verified Node Registry (domain/node_registry.json)

已驗證節點建立方式的單一來源：
- lookup_recipes(): get_node_recipe 工具的批次查詢（離線、不分大小寫、支援 badNames/aliases）
- resolve_create_name(): search_nodes 顯示「真正可建立節點」的名稱
- correct_instruction_names(): 執行前把已知錯誤名稱改成 registry 的 create
- learn_from_execution(): 成功執行後自動學習（status = "auto-verified"），建立失敗則記錄 badNames

本模組不依賴 websockets，可直接單元測試。
"""
import difflib
import json
import os
import re
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

REGISTRY_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "domain", "node_registry.json"))

AUTO_STATUS = "auto-verified"
AUTO_FAILED_STATUS = "auto-failed"
_AUTO_STATUSES = (AUTO_STATUS, AUTO_FAILED_STATUS)

_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_CREATE_FAILED_RE = re.compile(r"\[CreateNode Failed\]\s*(.*?)\s*\(ID:\s*([^)]*)\)")

_write_lock = threading.Lock()


# ------------------------------------------
# 載入 / 寫入
# ------------------------------------------

def load_registry(path: str = None) -> dict:
    path = path or REGISTRY_PATH
    if not os.path.exists(path):
        return {"globalRules": [], "nodes": {}, "patterns": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("globalRules", [])
    data.setdefault("nodes", {})
    data.setdefault("patterns", {})
    return data


def dumps_registry(reg: dict) -> str:
    """固定格式：每個節點一行，方便 git diff 與人工編輯。"""
    def one(v):
        return json.dumps(v, ensure_ascii=False)

    parts = []
    for key, value in reg.items():
        if key == "nodes" and isinstance(value, dict):
            body = ",\n".join(f"    {one(k)}: {one(v)}" for k, v in value.items())
            parts.append(f"  {one(key)}: {{\n{body}\n  }}" if body else f"  {one(key)}: {{}}")
        elif key == "globalRules" and isinstance(value, list):
            body = ",\n".join(f"    {one(r)}" for r in value)
            parts.append(f"  {one(key)}: [\n{body}\n  ]" if body else f"  {one(key)}: []")
        else:
            nested = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ")
            parts.append(f"  {one(key)}: {nested}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def save_registry(reg: dict, path: str = None) -> None:
    """原子寫入：同目錄暫存檔 + os.replace。"""
    path = path or REGISTRY_PATH
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".node_registry.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps_registry(reg))
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# ------------------------------------------
# 索引 / 查詢
# ------------------------------------------

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _query_variants(query: str) -> List[str]:
    """查詢字串的候選形式：原樣、去掉 @簽章、fullName 的最後兩段（DSCoreNodes.DSCore.String.Split -> String.Split）。"""
    q = _norm(query)
    variants = [q]
    base = q.split("@", 1)[0]
    if base not in variants:
        variants.append(base)
    segs = [s for s in base.split(".") if s]
    if len(segs) >= 3:
        tail = ".".join(segs[-2:])
        if tail not in variants:
            variants.append(tail)
    return [v for v in variants if v]


def build_index(reg: dict) -> Dict[str, tuple]:
    """norm(name) -> (registry key, matchedBy)。優先序：key > create > aliases/creationName > badNames。"""
    index: Dict[str, tuple] = {}
    nodes = reg.get("nodes", {})
    tiers = [
        ("name", lambda k, e: [k]),
        ("create", lambda k, e: [e.get("create")]),
        ("alias", lambda k, e: list(e.get("aliases") or []) + [e.get("creationName"), e.get("nodeName")]),
        ("badName", lambda k, e: list(e.get("badNames") or [])),
    ]
    for tier, getter in tiers:
        for key, entry in nodes.items():
            for candidate in getter(key, entry):
                n = _norm(candidate)
                if n and n not in index:
                    index[n] = (key, tier)
    return index


def _find(reg: dict, index: dict, query: str) -> Optional[tuple]:
    for v in _query_variants(query):
        if v in index:
            return index[v]
    return None


def _format_ports(ports) -> str:
    if not ports:
        return "—"
    return ", ".join(f"{i}:{p if p != '' else '(unnamed)'}" for i, p in enumerate(ports))


def lookup_recipes(names: List[str], path: str = None, include_rules: bool = True) -> dict:
    reg = load_registry(path)
    index = build_index(reg)
    nodes = reg["nodes"]
    found, missing, patterns = [], [], []

    pattern_keys = {_norm(k): k for k in reg.get("patterns", {})}
    for query in names or []:
        hit = _find(reg, index, query)
        if hit:
            key, matched_by = hit
            entry = nodes[key]
            item = {"query": query, "name": key, "matchedBy": matched_by}
            item.update(entry)
            q = _norm(query)
            bad = {_norm(b) for b in entry.get("badNames") or []}
            if (q in bad or matched_by == "badName") and _norm(entry.get("create")) != q:
                item["warning"] = f"'{query}' 不能直接建立節點" + (f"，請用 create: {entry.get('create')}" if entry.get("create") else "")
            found.append(item)
        elif _norm(query) in pattern_keys:
            pk = pattern_keys[_norm(query)]
            patterns.append({"name": pk, "pattern": reg["patterns"][pk]})
        else:
            all_names = list(nodes.keys())
            close = difflib.get_close_matches(query, all_names, n=3, cutoff=0.6)
            if not close:
                lower = {k.lower(): k for k in all_names}
                close = [lower[c] for c in difflib.get_close_matches(query.lower(), list(lower), n=3, cutoff=0.6)]
            missing.append({"query": query, "didYouMean": close})

    return {
        "globalRules": reg.get("globalRules", []) if include_rules else [],
        "found": found,
        "missing": missing,
        "patterns": patterns,
    }


def format_recipes(result: dict) -> str:
    found, missing = result["found"], result["missing"]
    total = len(found) + len(missing) + len(result["patterns"])
    lines = [f"[RECIPE] {len(found)}/{total} 個節點在 registry 中（domain/node_registry.json）"]

    if result["globalRules"]:
        lines.append("\n## 全域規則")
        lines.extend(f"{i}. {r}" for i, r in enumerate(result["globalRules"], 1))

    for item in found:
        status = item.get("status") or "manual"
        head = f"\n## {item['name']}"
        if _norm(item["query"]) != _norm(item["name"]):
            head += f"  (查詢: {item['query']})"
        lines.append(head)
        if item.get("create"):
            lines.append(f"create: `{item['create']}`")
        else:
            lines.append("create: （未知 — 此名稱曾建立失敗，請用 search_nodes 找正確名稱）")
        if item.get("warning"):
            lines.append(f"[WARNING] {item['warning']}")
        if "inputs" in item or "outputs" in item:
            lines.append(f"inputs: {_format_ports(item.get('inputs'))} | outputs: {_format_ports(item.get('outputs'))}")
        if item.get("value"):
            lines.append(f"value: {item['value']}")
        if item.get("badNames"):
            lines.append("badNames（勿用）: " + ", ".join(item["badNames"]))
        for g in item.get("gotchas") or []:
            lines.append(f"- 陷阱: {g}")
        verified = item.get("verified") or "?"
        extra = f", resolved: {item['creationName']}" if status in _AUTO_STATUSES and item.get("creationName") else ""
        lines.append(f"verified: {verified} [{status}{extra}]")

    for p in result["patterns"]:
        lines.append(f"\n## 模式: {p['name']}\n{p['pattern']}")

    if missing:
        lines.append("\n## 不在 registry（請對這些名稱使用 search_nodes，並使用其 create 欄位）")
        for m in missing:
            hint = f"  可能是: {', '.join(m['didYouMean'])}" if m["didYouMean"] else ""
            lines.append(f"- {m['query']}{hint}")

    return "\n".join(lines)


def resolve_create_name(name: str, full_name: str, creation_name: str, reg: dict = None, index: dict = None) -> tuple:
    """search_nodes 用：回傳 (可建立的名稱, 來源)。fullName 本身無法用於 CreateNodeCommand。"""
    reg = reg if reg is not None else load_registry()
    index = index if index is not None else build_index(reg)
    for candidate in (creation_name, full_name):
        if not candidate:
            continue
        hit = _find(reg, index, candidate)
        if hit and hit[1] != "badName":
            entry = reg["nodes"][hit[0]]
            if entry.get("create"):
                return entry["create"], "registry"
    if creation_name and creation_name != full_name:
        return creation_name, "creationName"
    segs = [s for s in (full_name or "").split("@", 1)[0].split(".") if s]
    if len(segs) >= 2:
        return ".".join(segs[-2:]), "short"
    return name or full_name, "name"


def correct_instruction_names(instr_nodes: list, path: str = None) -> list:
    """執行前修正：若名稱是某節點的 badName 且該節點有 create，替換為 create。回傳修正清單。"""
    reg = load_registry(path)
    index = build_index(reg)
    corrections = []
    for node in instr_nodes or []:
        name = node.get("name")
        if not name or node.get("creationName"):
            continue
        hit = _find(reg, index, name)
        if not hit:
            continue
        entry = reg["nodes"][hit[0]]
        create = entry.get("create")
        bad = {_norm(b) for b in entry.get("badNames") or []}
        if create and _norm(name) in bad and _norm(create) != _norm(name):
            node["name"] = create
            corrections.append({"id": node.get("id", ""), "from": name, "to": create})
    return corrections


# ------------------------------------------
# 自動學習
# ------------------------------------------

def is_guid(text: str) -> bool:
    return bool(_GUID_RE.match(str(text or "")))


def parse_failed_creations(errors) -> Dict[str, str]:
    """從 C# 'Partial failure' errors 解析 {id: name}。"""
    failed = {}
    for e in errors or []:
        m = _CREATE_FAILED_RE.search(str(e))
        if m:
            failed[m.group(2).strip().lower()] = m.group(1).strip()
    return failed


def learn_from_execution(
    instr_nodes: list,
    pre_existing_ids: set,
    graph_nodes: list,
    structured_nodes: list,
    errors: list = None,
    dynamo_version: str = None,
    skip_ids: set = None,
    path: str = None,
) -> dict:
    """
    instr_nodes: 實際送出的節點（name 為最終使用名稱）
    pre_existing_ids: 執行前已存在的節點 GUID（小寫）— 這些只是 upsert，無法驗證名稱，略過
    graph_nodes: 執行後 get_graph_status 的 nodes（含 creationName）
    structured_nodes: 執行後 get_nodes_structured 的 nodes（含 inputs/outputs 埠名）
    skip_ids: 不學習的節點 id（例如外掛 GUID 映射節點）
    """
    pre_existing_ids = {str(i).lower() for i in (pre_existing_ids or set())}
    skip_ids = {str(i).lower() for i in (skip_ids or set())}
    graph = {str(n.get("id", "")).lower(): n for n in graph_nodes or []}
    struct = {str(n.get("id", "")).lower(): n for n in structured_nodes or []}
    failed_by_id = parse_failed_creations(errors)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    version = dynamo_version or "unknown"

    learned, bad, skipped = [], [], []

    with _write_lock:
        reg = load_registry(path)
        nodes = reg["nodes"]
        index = build_index(reg)
        changed = False

        def find_entry(name):
            hit = _find(reg, index, name)
            return hit if hit else (None, None)

        for node in instr_nodes or []:
            nid = str(node.get("id", "")).lower()
            name = str(node.get("name", "")).strip()
            if not name or not is_guid(nid) or nid in skip_ids or nid in pre_existing_ids:
                continue

            key, matched_by = find_entry(name)
            entry = nodes.get(key) if key else None
            created = nid in graph and nid not in failed_by_id

            if not created:
                # 建立失敗：記錄 badName
                if entry is None:
                    nodes[name] = {
                        "create": None,
                        "badNames": [name],
                        "gotchas": ["此名稱無法建立節點；請用 search_nodes 並使用其 create 欄位"],
                        "status": AUTO_FAILED_STATUS,
                        "verified": f"{version} ({now})",
                    }
                    changed = True
                    bad.append(name)
                elif _norm(name) != _norm(entry.get("create")):
                    lst = entry.setdefault("badNames", [])
                    if _norm(name) not in {_norm(b) for b in lst}:
                        lst.append(name)
                        changed = True
                    bad.append(name)
                else:
                    skipped.append({"name": name, "reason": "registry create 名稱本次建立失敗（未修改，請檢查）"})
                continue

            # 建立成功
            if matched_by == "badName":
                skipped.append({"name": name, "reason": f"屬於 {key} 的 badNames，建出的節點可能不是預期的"})
                continue
            if entry is not None and entry.get("status") not in _AUTO_STATUSES:
                continue  # 人工驗證項目：不覆寫

            g = graph.get(nid, {})
            s = struct.get(nid, {})
            target_key = key or name
            target = nodes.get(target_key, {})
            target["create"] = name
            if s.get("inputs") is not None:
                target["inputs"] = [p.get("name", "") for p in s.get("inputs") or []]
            if s.get("outputs") is not None:
                target["outputs"] = [p.get("name", "") for p in s.get("outputs") or []]
            if g.get("creationName"):
                target["creationName"] = g["creationName"]
            if g.get("name"):
                target["nodeName"] = g["name"]
            if target.get("badNames"):
                target["badNames"] = [b for b in target["badNames"] if _norm(b) != _norm(name)]
                if not target["badNames"]:
                    target.pop("badNames")
            if target.get("status") == AUTO_FAILED_STATUS:
                target.pop("gotchas", None)
            target["status"] = AUTO_STATUS
            target["verified"] = f"{version} ({now})"
            nodes[target_key] = target
            changed = True
            learned.append(target_key)

        if changed:
            save_registry(reg, path)

    return {"learned": learned, "badNames": bad, "skipped": skipped}


# ------------------------------------------
# Dynamo 版本偵測（Windows：讀取 Dynamo 程序載入的 DynamoCore.dll 檔案版本）
# ------------------------------------------

_version_cache: Dict[int, str] = {}


def detect_dynamo_version(process_id) -> Optional[str]:
    try:
        pid = int(process_id)
    except (TypeError, ValueError):
        return None
    if pid in _version_cache:
        return _version_cache[pid]
    version = None
    if os.name == "nt":
        # DynamoCore.dll 為 managed 組件，不會出現在 Modules；改由原生模組路徑找出 Dynamo 資料夾再讀檔案版本
        cmd = (
            f"$p = Get-Process -Id {pid} -ErrorAction Stop; "
            "$dirs = $p.Modules | ForEach-Object { $_.FileName } | "
            "Where-Object { $_ -match '\\\\(DynamoForRevit|Dynamo Core\\\\[0-9.]+|Dynamo)\\\\' } | "
            "ForEach-Object { $_.Substring(0, $_.IndexOf($matches[0]) + $matches[0].Length) } | Select-Object -Unique; "
            "foreach ($d in $dirs) { $f = Join-Path $d 'DynamoCore.dll'; "
            "if (Test-Path $f) { (Get-Item $f).VersionInfo.FileVersion; break } }; "
            "$host_ = $p.MainModule.FileName; "
            "if ($host_ -match 'Revit (\\d{4})') { 'Revit ' + $matches[1] } else { $p.ProcessName }"
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip().splitlines()
            out = [o.strip() for o in out if o.strip()]
            if out:
                dyn = next((o for o in out if re.match(r"^\d+\.\d+", o)), None)
                host = next((o for o in out if not re.match(r"^\d+\.\d+", o)), None)
                if dyn:
                    short = ".".join(dyn.split(".")[:2])
                    version = f"Dynamo {short}" + (f" / {host}" if host else "")
        except Exception:
            version = None
    _version_cache[pid] = version
    return version
