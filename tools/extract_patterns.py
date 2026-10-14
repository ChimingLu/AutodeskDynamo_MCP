"""
從 .dyn 擷取可重用的連接模式，去識別化後存進 domain/node_registry.json（status "captured"）。

離線可用：直接讀 .dyn，不需要 Dynamo 或 Revit。DynamoSandbox 把 Revit 節點顯示成 Legacy Node，
這裡改用 .dyn 的 FunctionSignature / UI 類別名稱當建立名稱。

1) 列出候選節點鏈（依群組與連通子圖切分，並標出與既有模式重複者）：
    python tools/extract_patterns.py path/to/script.dyn
2) 寫一份 spec JSON（見 docs/ai-guide/extract-patterns.md），先預覽、再寫入：
    python tools/extract_patterns.py path/to/script.dyn --spec spec.json
    python tools/extract_patterns.py path/to/script.dyn --spec spec.json --write

即時工作區：先用 MCP get_graph_status 取得 workspace.fileName（請使用者先 Ctrl+S），再把該路徑傳進來。
"""
import argparse
import getpass
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "bridge", "python"))

import node_registry  # noqa: E402

PATH_PLACEHOLDER = "C:/path/to/input"
REDACTED = "<redacted>"
_WIN_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\\/\s\"']+[\\/])[^\"'\r\n;]*")
_GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:-[0-9a-fA-F]{8})?\b")
_GUID_KEYS = ("name",)  # 自訂節點的 function GUID 是套件定義，必須保留


# ------------------------------------------
# 讀取 .dyn
# ------------------------------------------

def load_dyn(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    if text.lstrip().startswith("<"):
        raise SystemExit("這是 Dynamo 1.x 的 XML 格式 .dyn：請在 Dynamo 2.x「另存新檔」到其他位置（勿覆蓋原檔）後再擷取")
    return json.loads(text)


def graph_from_dyn(dyn: dict) -> tuple:
    """轉成與 get_graph_status 相同形狀的 (nodes, connectors, groups)，Revit 節點以 FunctionSignature 為建立名稱。"""
    views = {v["Id"]: v for v in (dyn.get("View") or {}).get("NodeViews") or []}
    owner, nodes = {}, []
    for n in dyn.get("Nodes") or []:
        nid = n["Id"]
        for i, p in enumerate(n.get("Inputs") or []):
            owner[p["Id"]] = (nid, i)
        for i, p in enumerate(n.get("Outputs") or []):
            owner[p["Id"]] = (nid, i)
        ctype = n.get("ConcreteType", "").split(",")[0]
        if "CodeBlockNodeModel" in ctype:
            full, creation = "Dynamo.Graph.Nodes.CodeBlockNodeModel", "Code Block"
        elif ctype.startswith(node_registry._GENERIC_NODE_TYPES):
            full, creation = ctype, n.get("FunctionSignature", "")
        else:
            full, creation = ctype, ""
        v = views.get(nid, {})
        nodes.append({"id": nid, "name": v.get("Name") or ctype, "fullName": full, "creationName": creation,
                      "x": v.get("X", 0), "y": v.get("Y", 0)})
    connectors = []
    for c in dyn.get("Connectors") or []:
        if c.get("Start") in owner and c.get("End") in owner:
            (f, fp), (t, tp) = owner[c["Start"]], owner[c["End"]]
            connectors.append({"from": f, "fromPort": fp, "to": t, "toPort": tp})
    groups = [{"title": a.get("Title") or "", "nodes": a.get("Nodes") or []}
              for a in (dyn.get("View") or {}).get("Annotations") or [] if a.get("Nodes")]
    return nodes, connectors, groups


def ports_from_dyn(dyn: dict) -> list:
    """與 get_nodes_structured 相同形狀的輸入埠資訊；有輸入埠的 UI 節點（例 All Elements of Category）才不會被誤判為缺值。"""
    return [{"id": n["Id"], "inputs": [p.get("Name") for p in n.get("Inputs") or []]} for n in dyn.get("Nodes") or []]


def components(nodes: list, connectors: list) -> list:
    """連通子圖（忽略方向），由大到小。"""
    parent = {n["id"]: n["id"] for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for c in connectors:
        parent[find(c["from"])] = find(c["to"])
    comp = defaultdict(list)
    for n in nodes:
        comp[find(n["id"])].append(n["id"])
    return sorted(comp.values(), key=len, reverse=True)


# ------------------------------------------
# 去識別化
# ------------------------------------------

def sensitive_terms(dyn_path: str, extra: list = None) -> list:
    """會被換成 <redacted> 的字串：使用者名稱、.dyn 檔名、所在資料夾名稱、OneDrive 組織名稱、額外指定詞。"""
    terms = set(t for t in (extra or []) if t)
    try:
        terms.add(getpass.getuser())
    except Exception:
        pass
    stem = os.path.splitext(os.path.basename(dyn_path))[0]
    terms.update([stem, os.path.basename(os.path.dirname(os.path.abspath(dyn_path)))])
    for part in re.split(r"[\\/]", os.path.abspath(dyn_path)):
        if part.lower().startswith("onedrive - "):
            terms.update([part, part[len("onedrive - "):]])
    return sorted((t for t in terms if len(t) >= 3), key=len, reverse=True)


def redact_text(text: str, terms: list, log: list) -> str:
    out = _WIN_PATH.sub(lambda m: (log.append(f"路徑 → {PATH_PLACEHOLDER}"), PATH_PLACEHOLDER)[1], text)
    out = _GUID.sub(lambda m: (log.append("GUID/UniqueId → <guid>"), "<guid>")[1], out)
    for t in terms:
        if t in out:
            out = out.replace(t, REDACTED)
            log.append(f"敏感字串（{len(t)} 字元）→ {REDACTED}")
    return out


def redact(obj, terms: list, log: list, key: str = None):
    if isinstance(obj, str):
        return obj if key in _GUID_KEYS else redact_text(obj, terms, log)
    if isinstance(obj, list):
        return [redact(v, terms, log, key) for v in obj]
    if isinstance(obj, dict):
        return {k: redact(v, terms, log, k) for k, v in obj.items()}
    return obj


def leftovers(obj, terms: list) -> list:
    """寫入前最後檢查：仍含路徑或敏感字串就拒絕寫入。"""
    texts = []

    def walk(o):
        if isinstance(o, str):
            texts.append(o)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)  # 逐字串檢查，避免 JSON 跳脫（例 "s:\n"）被誤判成路徑
    found = [t for t in terms if any(t in s for s in texts)]
    if any(_WIN_PATH.search(s.replace(PATH_PLACEHOLDER, "")) for s in texts):
        found.append("Windows 路徑")
    return found


# ------------------------------------------
# 去重
# ------------------------------------------

_CONTENT_NODES = ("code block", "python")
_PLACEHOLDER = re.compile(r"C:/path/to/[^\"'\s;]*|<redacted>|<guid>")


def _content(node: dict) -> str:
    """Code Block / Python 的內容：壓縮空白；路徑、GUID、已去識別化的值一律視為相同。"""
    text = node.get("pythonCode") or node.get("value") or ""
    text = _PLACEHOLDER.sub("<v>", _GUID.sub("<v>", _WIN_PATH.sub("<v>", str(text))))
    return re.sub(r"\s+", " ", text).strip()


def _token(node: dict) -> str:
    name = node_registry._norm(node.get("name"))
    if any(k in str(node.get("name", "")).lower() for k in _CONTENT_NODES) or "pythonCode" in node:
        return f"{name}|{_content(node)}"
    return name


def pattern_signature(nodes: list, connectors: list) -> Counter:
    """節點（含 Code Block / Python 內容）＋連線 (from, fromPort, to, toPort) 的多重集合。nodes 以 id 或 ref 對應連線。"""
    tok = {str(n.get("ref") or n.get("id")).lower(): _token(n) for n in nodes}
    sig = Counter(("node", t) for t in tok.values())
    for c in connectors or []:
        a, b = tok.get(str(c.get("from")).lower()), tok.get(str(c.get("to")).lower())
        if a and b:
            sig[("edge", a, int(c.get("fromPort", 0)), b, int(c.get("toPort", 0)))] += 1
    return sig


MIN_CONTAINED_NODES = 3  # 太小的鏈（例：FilterByBoolMask→Flatten）到處都包含得到，不列為包含


def _node_count(sig: Counter) -> int:
    return sum(v for k, v in sig.items() if k[0] == "node")


def compare_signatures(a: Counter, b: Counter) -> tuple:
    """回傳 (相似度, 關係)。關係：相同 / 包含於（a ⊆ b）/ 包含（b ⊆ a）/ 相似。"""
    if not a or not b:
        return 0.0, ""
    score = sum((a & b).values()) / sum((a | b).values())
    if a == b:
        return 1.0, "相同"
    if not (a - b) and _node_count(a) >= MIN_CONTAINED_NODES:
        return score, "包含於"
    if not (b - a) and _node_count(b) >= MIN_CONTAINED_NODES:
        return score, "包含"
    return score, "相似"


def similar_patterns(nodes: list, connectors: list, reg: dict, threshold: float = 0.6, exclude: str = None) -> list:
    """以節點＋內容＋連線比對既有模式，回傳 [(名稱, 相似度, 關係)]；完全包含者不論相似度都列出。"""
    mine = pattern_signature(nodes, connectors)
    hits = []
    for name, p in reg.get("patterns", {}).items():
        if name == exclude or not node_registry.is_structured_pattern(p):
            continue
        score, rel = compare_signatures(mine, pattern_signature(p["nodes"], p.get("connectors")))
        if rel in ("相同", "包含於", "包含") or score >= threshold:
            hits.append((name, round(score, 2), rel))
    return sorted(hits, key=lambda h: -h[1])


def check_registry(reg: dict, threshold: float = 0.6) -> list:
    """全 registry 兩兩比對：[(A, B, 相似度, 關係)]，關係以 A 對 B 表示。"""
    pats = [(k, pattern_signature(p["nodes"], p.get("connectors")))
            for k, p in reg.get("patterns", {}).items() if node_registry.is_structured_pattern(p)]
    out = []
    for i, (a, sa) in enumerate(pats):
        for b, sb in pats[i + 1:]:
            score, rel = compare_signatures(sa, sb)
            if rel in ("相同", "包含於", "包含") or score >= threshold:
                out.append((a, b, round(score, 2), rel))
    return sorted(out, key=lambda h: -h[2])


# ------------------------------------------
# 主流程
# ------------------------------------------

def resolve_ids(prefixes: list, nodes: list) -> list:
    out = []
    for p in prefixes:
        p = node_registry._plain_id(p)
        hit = [n["id"] for n in nodes if node_registry._plain_id(n["id"]).startswith(p)]
        if len(hit) != 1:
            raise SystemExit(f"節點 id 前綴 {p} 對到 {len(hit)} 個節點")
        out.append(hit[0])
    return out


def list_candidates(nodes, connectors, groups, reg, dyn=None):
    by_id = {n["id"]: n for n in nodes}
    values = node_registry.read_dyn_values(dyn) if dyn else {}
    index = node_registry.build_index(reg)
    create = {n["id"]: node_registry.choose_create_name(n, reg, index)[0] for n in nodes}
    linked = {c["from"] for c in connectors} | {c["to"] for c in connectors}
    sets = [(f"群組「{g['title']}」", [i for i in g["nodes"] if i in by_id]) for g in groups]
    sets += [(f"連通子圖 {k + 1}", ids) for k, ids in enumerate(components(nodes, connectors)) if len(ids) >= 3]
    for label, ids in sets:
        print(f"\n== {label}（{len(ids)} 個節點）")
        for i in ids:
            print(f"   {i[:8]}  {by_id[i]['name']}  →  {create[i]}")
        cand = [dict(values.get(node_registry._plain_id(i), {}), id=i, name=create[i]) for i in ids]
        idset = set(ids)
        for name, score, rel in similar_patterns(cand, [c for c in connectors if c["from"] in idset and c["to"] in idset], reg):
            print(f"   ⚠ 與既有模式「{name}」{rel}（相似度 {score}）")
    lonely = [by_id[i]["name"] for i in by_id if i not in linked]
    if lonely:
        print(f"\n未接線的節點（通常不收）: {', '.join(lonely)}")


def run_spec(dyn_path, dyn, nodes, connectors, reg, spec, write, extra_terms):
    terms = sensitive_terms(dyn_path, extra_terms + list(spec.get("redact") or []))
    for item in spec["patterns"]:
        log = []
        built = node_registry.build_pattern_from_workspace(nodes, connectors, resolve_ids(item["nodes"], nodes),
                                                           ports_from_dyn(dyn), dyn, reg)
        gotchas = list(item.get("gotchas") or []) + [f"模式外輸入: {e}" for e in built["externalInputs"]]
        instr = redact(built["instructions"], terms, log)
        desc, keywords, gotchas = (redact(x, terms, log) for x in (item.get("description", ""),
                                                                    item.get("keywords") or [], gotchas))
        name = item["name"]
        print(f"\n== {name}: {len(instr['nodes'])} 個節點 / {len(instr['connectors'])} 條連線")
        for n in instr["nodes"]:
            print(f"   {n['name']}  {n.get('value', '')}")
        for g in gotchas:
            print(f"   ! {g}")
        if built["packages"]:
            print(f"   外掛套件: {'; '.join(p['name'] + ' ' + p.get('version', '') for p in built['packages'])}")
        for w in built["warnings"]:
            print(f"   ⚠ {w}")
        for other, score, rel in similar_patterns(instr["nodes"], instr["connectors"], reg,
                                                  exclude=name if item.get("overwrite") else None):
            print(f"   ⚠ 與既有模式「{other}」{rel}（相似度 {score}）")
        if log:
            print(f"   去識別化: {'; '.join(sorted(set(log)))}")
        left = leftovers({"i": instr, "d": desc, "k": keywords, "g": gotchas}, terms)
        if left:
            print(f"   ✗ 仍含敏感內容（{', '.join(left)}），不寫入")
            continue
        if write:
            res = node_registry.save_pattern(name, instr, desc, keywords, gotchas, status="captured",
                                             overwrite=bool(item.get("overwrite")), packages=built["packages"])
            print(f"   → {res.get('status')}: {res.get('message', res.get('patternStatus'))}")


def main():
    ap = argparse.ArgumentParser(description="從 .dyn 擷取並去識別化連接模式")
    ap.add_argument("dyn", nargs="?", help=".dyn 路徑（即時工作區請用 get_graph_status 的 workspace.fileName）")
    ap.add_argument("--check-registry", action="store_true", help="不讀 .dyn，檢查 registry 內模式的重複／包含關係")
    ap.add_argument("--spec", help="要存的模式清單 JSON；未提供則只列出候選節點鏈")
    ap.add_argument("--write", action="store_true", help="實際寫入 node_registry.json（預設只預覽）")
    ap.add_argument("--redact", action="append", default=[], help="額外要遮蔽的字串（專案名、業主名…），可重複")
    args = ap.parse_args()

    if args.check_registry:
        rows = check_registry(node_registry.load_registry())
        for a, b, score, rel in rows:
            label = {"包含於": "⊆", "包含": "⊇", "相同": "＝"}.get(rel, "~")
            print(f"[{rel}] {a} {label} {b}（相似度 {score}）")
        print(f"\n共 {len(rows)} 組（關係以左邊對右邊表示；相似門檻 0.6）")
        return
    if not args.dyn:
        ap.error("需要 .dyn 路徑，或使用 --check-registry")
    dyn = load_dyn(args.dyn)
    nodes, connectors, groups = graph_from_dyn(dyn)
    reg = node_registry.load_registry()
    if not args.spec:
        list_candidates(nodes, connectors, groups, reg, dyn)
        return
    with open(args.spec, "r", encoding="utf-8-sig") as f:
        spec = json.load(f)
    run_spec(args.dyn, dyn, nodes, connectors, reg, spec, args.write, args.redact)
    if not args.write:
        print("\n（預覽模式，未寫入；確認後加 --write）")


if __name__ == "__main__":
    main()
