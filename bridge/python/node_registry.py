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
        "relatedPatterns": patterns_using(reg, [f["name"] for f in found]),
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
        body = p["pattern"]
        if is_structured_pattern(body):
            body = (body.get("description") or "") + f"\n（結構化連接模式：用 get_node_pattern(\"{p['name']}\") 取得可直接執行的 JSON）"
        lines.append(f"\n## 模式: {p['name']}\n{body}")

    shown = {p["name"] for p in result["patterns"]}
    related = [r for r in result.get("relatedPatterns") or [] if r not in shown]
    if related:
        lines.append("\n## 相關連接模式（get_node_pattern 可直接取得含連線的 JSON）")
        lines.extend(f"- {r}" for r in related)

    if missing:
        lines.append("\n## 不在 registry（請對這些名稱使用 search_nodes，並使用其 create 欄位）")
        for m in missing:
            hint = f"  可能是: {', '.join(m['didYouMean'])}" if m["didYouMean"] else ""
            lines.append(f"- {m['query']}{hint}")

    return "\n".join(lines)


def resolve_create_name(name: str, full_name: str, creation_name: str, reg: dict = None, index: dict = None,
                        element_type: str = "") -> tuple:
    """search_nodes 用：回傳 (可建立的名稱, 來源)。fullName 本身無法用於 CreateNodeCommand。
    element_type 為 C# list_nodes 的 type（例：NodeModelSearchElement）；UI 節點只能用顯示名稱建立
    （Dynamo 2.6 實測：'Categories' 可建立，'Selection.Categories' 不行）。"""
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
    is_ui_node = "nodemodel" in (element_type or "").lower()
    if is_ui_node and name:
        hit = _find(reg, index, name)
        if hit and hit[1] != "badName":
            if reg["nodes"][hit[0]].get("create"):
                return reg["nodes"][hit[0]]["create"], "registry"
            return name, "ambiguous"  # 已知此顯示名稱會建出別的節點
    if creation_name and creation_name != full_name:
        return creation_name, "creationName"
    if is_ui_node and name:
        return name, "name"
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


def _strip_sig(text) -> str:
    return _norm(text).split("@", 1)[0]


def name_matches_node(requested: str, graph_node: dict) -> bool:
    """建出的節點是否真的是要求的那個（排除 'String' 建出 FloatFormatHandling.String、'Views' 建出 Sheet.Views 這類同名誤判）。"""
    r = _strip_sig(requested)
    if not r or is_guid(requested):
        return True
    display = _strip_sig(graph_node.get("name"))
    exact = {display, _strip_sig(graph_node.get("creationName")), _strip_sig(graph_node.get("fullName"))}
    if r in exact:
        return True
    if display and r.endswith("." + display):  # Revit.Elements.Room.Name -> Room.Name
        return True
    creation = _strip_sig(graph_node.get("creationName"))
    # 帶命名空間的短名（List.Count -> DSCore.List.Count）；單字名稱太模糊，不接受後綴比對
    return "." in r and bool(creation) and creation.endswith("." + r)


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

    learned, bad, skipped, ambiguous = [], [], [], []

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

            # 建出來的不是同名節點（同名誤判）：視同錯誤名稱
            g = graph.get(nid, {})
            if not name_matches_node(name, g):
                resolved = g.get("creationName") or g.get("name") or g.get("fullName")
                note = f"此名稱會建出 {g.get('name')}（{resolved}），不是預期的同名節點"
                if entry is None or (entry.get("status") in _AUTO_STATUSES and _norm(entry.get("create")) == _norm(name)):
                    nodes[key or name] = {
                        "create": None, "badNames": [name], "gotchas": [note], "resolvedTo": resolved,
                        "status": AUTO_FAILED_STATUS, "verified": f"{version} ({now})",
                    }
                    changed = True
                elif _norm(name) != _norm(entry.get("create")):
                    lst = entry.setdefault("badNames", [])
                    if _norm(name) not in {_norm(b) for b in lst}:
                        lst.append(name)
                        changed = True
                ambiguous.append({"name": name, "createdInstead": resolved})
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

    return {"learned": learned, "badNames": bad, "ambiguous": ambiguous, "skipped": skipped}


# ------------------------------------------
# 連接模式（patterns）：常用的節點組合 + 連線，可直接實例化成 execute_dynamo_instructions JSON
# ------------------------------------------
# 結構化模式格式：
#   "名稱": {"description", "keywords": [], "nodes": [{"ref", "name", "value"?, "x", "y", ...}],
#            "connectors": [{"from": ref, "fromPort", "to": ref, "toPort"}], "gotchas": [], "status", "verified"}
# 舊的文字模式（"名稱": "說明文字"）仍相容，只回傳說明。

_PATTERN_NODE_DROP = {"id", "x", "y", "_strategy"}


def is_structured_pattern(pattern) -> bool:
    return isinstance(pattern, dict) and isinstance(pattern.get("nodes"), list)


def search_patterns(query: str, path: str = None, reg: dict = None, limit: int = 3) -> List[tuple]:
    """依名稱/關鍵字/節點名稱打分，回傳 [(name, pattern, score)]。query 可為中文句子。"""
    reg = reg if reg is not None else load_registry(path)
    q = _norm(query)
    scored = []
    for name, pattern in reg.get("patterns", {}).items():
        n = _norm(name)
        score = 0
        if not q:
            score = 1
        elif q == n:
            score = 100
        elif q in n or n in q:
            score = 60
        if q and isinstance(pattern, dict):
            for kw in pattern.get("keywords") or []:
                k = _norm(kw)
                if k and (k in q or q in k):
                    score += 10
            for node in pattern.get("nodes") or []:
                nn = _norm(node.get("name"))
                if nn and len(nn) > 3 and (nn in q or q in nn):
                    score += 5
        elif q and isinstance(pattern, str) and q in _norm(pattern):
            score += 5
        if score:
            scored.append((name, pattern, score))
    scored.sort(key=lambda t: -t[2])
    return scored if not q else scored[:limit]


def instantiate_pattern(pattern: dict, base_x: float = 0, base_y: float = 0, id_factory=None) -> dict:
    """產生可直接送 execute_dynamo_instructions 的 JSON（每次新 GUID）。回傳 {"instructions", "ids": {ref: guid}}。"""
    import uuid
    id_factory = id_factory or (lambda: str(uuid.uuid4()))
    ids = {}
    nodes = []
    for node in pattern.get("nodes") or []:
        ref = node["ref"]
        ids[ref] = id_factory()
        out = {"id": ids[ref]}
        out.update({k: v for k, v in node.items() if k not in ("ref", "x", "y", "note")})
        out["x"] = float(node.get("x", 0)) + base_x
        out["y"] = float(node.get("y", 0)) + base_y
        nodes.append(out)
    connectors = []
    for c in pattern.get("connectors") or []:
        if c.get("from") in ids and c.get("to") in ids:
            connectors.append({"from": ids[c["from"]], "fromPort": c.get("fromPort", 0),
                               "to": ids[c["to"]], "toPort": c.get("toPort", 0)})
    return {"instructions": {"nodes": nodes, "connectors": connectors}, "ids": ids}


def format_patterns(matches: List[tuple], base_x: float = 0, base_y: float = 0) -> str:
    if not matches:
        return "[PATTERN] 找不到符合的連接模式。可用 get_node_recipe 查節點，建好後用 save_node_pattern 存成模式。"
    lines = [f"[PATTERN] 找到 {len(matches)} 個連接模式"]
    for name, pattern, _ in matches:
        lines.append(f"\n## {name}")
        if not is_structured_pattern(pattern):
            lines.append(pattern if isinstance(pattern, str) else json.dumps(pattern, ensure_ascii=False))
            continue
        if pattern.get("description"):
            lines.append(pattern["description"])
        refs = {n["ref"]: n for n in pattern["nodes"]}
        for c in pattern.get("connectors") or []:
            a, b = refs.get(c["from"], {}), refs.get(c["to"], {})
            lines.append(f"- {a.get('name')}[{c.get('fromPort', 0)}] → {b.get('name')}[{c.get('toPort', 0)}]")
        for n in pattern["nodes"]:
            if n.get("note"):
                lines.append(f"- 註 {n['name']}: {n['note']}")
        for g in pattern.get("gotchas") or []:
            lines.append(f"- 陷阱: {g}")
        lines.append(f"verified: {pattern.get('verified', '?')} [{pattern.get('status', 'manual')}]")
        inst = instantiate_pattern(pattern, base_x, base_y)
        lines.append("instructions（新 GUID，可直接傳給 execute_dynamo_instructions；ids 可用來接其他節點）:")
        lines.append(json.dumps(inst["instructions"], ensure_ascii=False))
        lines.append("ids: " + json.dumps(inst["ids"], ensure_ascii=False))
    return "\n".join(lines)


def patterns_using(reg: dict, node_keys: List[str]) -> List[str]:
    """哪些結構化模式用到這些節點（以 registry key 或 create 比對）。"""
    wanted = set()
    for k in node_keys:
        wanted.add(_norm(k))
        entry = reg.get("nodes", {}).get(k) or {}
        if entry.get("create"):
            wanted.add(_norm(entry["create"]))
    hits = []
    for name, pattern in reg.get("patterns", {}).items():
        if is_structured_pattern(pattern) and any(_norm(n.get("name")) in wanted for n in pattern["nodes"]):
            hits.append(name)
    return hits


def _ref_for(name: str, used: set) -> str:
    base = re.sub(r"[^0-9a-zA-Z]+", "_", str(name or "node")).strip("_").lower() or "node"
    ref, i = base, 2
    while ref in used:
        ref, i = f"{base}{i}", i + 1
    used.add(ref)
    return ref


def check_pattern_in_graph(instructions: dict, graph_nodes: list, graph_connectors: list) -> List[str]:
    """確認 instructions 中的節點與連線確實存在於目前工作區；回傳問題清單（空 = 已驗證）。"""
    problems = []
    present = {str(n.get("id", "")).lower() for n in graph_nodes or []}
    for n in instructions.get("nodes", []):
        if str(n.get("id", "")).lower() not in present:
            problems.append(f"節點不在工作區: {n.get('name')} ({n.get('id')})")
    have = {(str(c.get("from", "")).lower(), int(c.get("fromPort", 0)), str(c.get("to", "")).lower(), int(c.get("toPort", 0)))
            for c in graph_connectors or []}
    for c in instructions.get("connectors", []):
        key = (str(c.get("from", "")).lower(), int(c.get("fromPort", 0)), str(c.get("to", "")).lower(), int(c.get("toPort", 0)))
        if key not in have:
            problems.append(f"連線不在工作區: {c.get('from')}[{key[1]}] → {c.get('to')}[{key[3]}]")
    return problems


def save_pattern(name: str, instructions: dict, description: str = "", keywords: List[str] = None,
                 gotchas: List[str] = None, problems: Optional[List[str]] = None, dynamo_version: str = None,
                 overwrite: bool = False, path: str = None) -> dict:
    """
    把一組已建好的 nodes/connectors 存成模式。problems=None 表示未對照工作區（status unverified），
    [] 表示已在工作區確認全部節點與連線存在（status verified）。
    """
    nodes_in = instructions.get("nodes") or []
    if not name or not nodes_in:
        return {"status": "error", "message": "需要 name 與至少一個節點"}
    min_x = min(float(n.get("x", 0)) for n in nodes_in)
    min_y = min(float(n.get("y", 0)) for n in nodes_in)
    used, ref_of, nodes = set(), {}, []
    for n in nodes_in:
        ref = _ref_for(n.get("name"), used)
        ref_of[str(n.get("id"))] = ref
        node = {"ref": ref}
        node.update({k: v for k, v in n.items() if k not in _PATTERN_NODE_DROP})
        node["x"] = round(float(n.get("x", 0)) - min_x)
        node["y"] = round(float(n.get("y", 0)) - min_y)
        nodes.append(node)
    connectors = []
    for c in instructions.get("connectors") or []:
        if str(c.get("from")) in ref_of and str(c.get("to")) in ref_of:
            connectors.append({"from": ref_of[str(c["from"])], "fromPort": int(c.get("fromPort", 0)),
                               "to": ref_of[str(c["to"])], "toPort": int(c.get("toPort", 0))})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pattern = {
        "description": description,
        "keywords": list(keywords or []),
        "nodes": nodes,
        "connectors": connectors,
        "gotchas": list(gotchas or []),
        "status": "verified" if problems == [] else "unverified",
        "verified": f"{dynamo_version or 'unknown'} ({now})" if problems == [] else None,
    }
    pattern = {k: v for k, v in pattern.items() if v not in (None, "", [])}
    with _write_lock:
        reg = load_registry(path)
        existing = reg["patterns"].get(name)
        if existing is not None and not overwrite:
            return {"status": "error", "message": f"模式「{name}」已存在；要覆寫請設 overwrite=true"}
        reg["patterns"][name] = pattern
        save_registry(reg, path)
    return {"status": "ok", "name": name, "patternStatus": pattern["status"], "problems": problems or [],
            "nodes": len(nodes), "connectors": len(connectors)}


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
