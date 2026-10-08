"""
Node Registry 實機驗證（需要 Dynamo 已連線、server.py 執行中）

證明 domain/node_registry.json 中每個節點的 create 名稱確實能建立節點、
埠名/埠順序與 registry 一致，且 badNames 確實無法建立（或建出不同的節點）。

執行: python tests/verify_node_registry_live.py [--keep] [--allow-nonempty]
  --keep            驗證後不清空工作區（方便目視檢查）
  --allow-nonempty  工作區不是空的也執行（驗證後不會清空）
結果寫入 tests/temp/node_registry_verification.json
"""
import argparse
import asyncio
import json
import os
import sys
import uuid

import websockets

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bridge", "python"))
import node_registry  # noqa: E402

BRIDGE_URL = "ws://127.0.0.1:65296"
REPORT_PATH = os.path.join(ROOT, "tests", "temp", "node_registry_verification.json")


class Bridge:
    def __init__(self, ws):
        self.ws = ws
        self.counter = 0

    async def call(self, name, **arguments):
        self.counter += 1
        req_id = f"verify_{self.counter}"
        await self.ws.send(json.dumps({"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                                       "params": {"name": name, "arguments": arguments}}))
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=120))
            if msg.get("id") == req_id:
                result = msg.get("result")
                if isinstance(result, str):
                    try:
                        return json.loads(result)
                    except ValueError:
                        return result
                return result

    async def graph(self):
        status = await self.call("get_graph_status")
        res = await self.call("read_dynamo_resource", resourceType="nodes")
        structured = res
        if isinstance(res, dict) and isinstance(res.get("contents"), list):
            structured = json.loads(res["contents"][0].get("text", "{}"))
        ports = {n["id"]: n for n in (structured or {}).get("nodes", [])}
        return {n["id"]: {**n, **ports.get(n["id"], {})} for n in status.get("nodes", [])}


def _port_names(node, side):
    return [p.get("name", "") for p in node.get(side) or []]


def _expected(entry, side):
    ports = entry.get(side)
    if ports is None or any("..." in p for p in ports):
        return None  # 未記錄或為描述性（例如 Python Script 的 IN[1]...）
    return ports


async def main(args):
    reg = node_registry.load_registry()
    async with websockets.connect(BRIDGE_URL, max_size=None) as ws:
        bridge = Bridge(ws)
        before = await bridge.call("get_graph_status")
        if not isinstance(before, dict) or "nodes" not in before:
            print(f"[FAIL] 無法取得 Dynamo 狀態（未連線？）: {before}")
            return 2
        started_empty = not before["nodes"]
        if not started_empty and not args.allow_nonempty:
            print(f"[ABORT] 工作區已有 {len(before['nodes'])} 個節點；請開啟空白工作區或加 --allow-nonempty")
            return 2

        # 1) 用 create 建立每個節點
        good = {}
        nodes = []
        for i, (key, entry) in enumerate(reg["nodes"].items()):
            if not entry.get("create"):
                continue
            gid = str(uuid.uuid4())
            good[gid] = key
            nodes.append({"id": gid, "name": entry["create"], "x": (i % 6) * 360, "y": (i // 6) * 260})
        r1 = await bridge.call("execute_dynamo_instructions", instructions=json.dumps({"nodes": nodes, "connectors": []}),
                               allow_fallback=False, clientId="registry-verify")
        after = await bridge.graph()

        results = []
        for gid, key in good.items():
            entry = reg["nodes"][key]
            node = after.get(gid)
            row = {"name": key, "create": entry["create"], "status": entry.get("status") or "manual"}
            if node is None:
                row.update(result="FAIL", reason="節點未建立")
            else:
                row.update(nodeName=node.get("name"), creationName=node.get("creationName"), fullName=node.get("fullName"))
                problems = []
                for side in ("inputs", "outputs"):
                    exp, act = _expected(entry, side), _port_names(node, side)
                    row[side] = act
                    if exp is not None and exp != act:
                        problems.append(f"{side}: registry={exp} 實際={act}")
                row.update(result="FAIL" if problems else "PASS", reason="; ".join(problems))
            results.append(row)

        # 2) badNames：應建立失敗，或建出與正確節點不同的類型
        bad_nodes, bad_meta = [], {}
        for i, (key, entry) in enumerate(reg["nodes"].items()):
            for bad in entry.get("badNames") or []:
                if node_registry._norm(bad) == node_registry._norm(entry.get("create")):
                    continue
                gid = str(uuid.uuid4())
                bad_meta[gid] = (key, bad)
                # creationName 覆寫可繞過 bridge 的自動更正，直接送出錯誤名稱
                bad_nodes.append({"id": gid, "name": bad, "creationName": bad,
                                  "x": 2500 + (len(bad_nodes) % 2) * 420, "y": (len(bad_nodes) // 2) * 260})
        if bad_nodes:
            await bridge.call("execute_dynamo_instructions", instructions=json.dumps({"nodes": bad_nodes, "connectors": []}),
                              allow_fallback=False, clientId="registry-verify")
            after2 = await bridge.graph()
            good_by_key = {k: after.get(g) for g, k in good.items()}
            for gid, (key, bad) in bad_meta.items():
                node = after2.get(gid)
                ref = good_by_key.get(key) or {}
                row = {"name": key, "badName": bad}
                if node is None:
                    row.update(result="PASS", reason="無法建立（符合 badNames）")
                elif (node.get("fullName"), node.get("creationName")) != (ref.get("fullName"), ref.get("creationName")):
                    row.update(result="PASS", reason=f"建出不同節點: {node.get('creationName') or node.get('fullName')}")
                else:
                    row.update(result="FAIL", reason="badName 竟建出與 create 相同的節點，可從 badNames 移除")
                results.append(row)

        # 3) 連接模式：實例化（新 GUID）→ 執行 → 確認全部節點與連線都在工作區
        pattern_rows = 0
        for name, pattern in reg.get("patterns", {}).items():
            if not node_registry.is_structured_pattern(pattern):
                continue
            inst = node_registry.instantiate_pattern(pattern, base_x=-2600, base_y=pattern_rows * 700)["instructions"]
            pattern_rows += 1
            await bridge.call("execute_dynamo_instructions", instructions=json.dumps(inst),
                              allow_fallback=False, clientId="registry-verify")
            status = await bridge.call("get_graph_status")
            problems = node_registry.check_pattern_in_graph(inst, status.get("nodes"), status.get("connectors"))
            if not problems and pattern.get("status") != "verified":
                # captured / unverified 模式實機建立成功 -> 升級為 verified
                node_registry.mark_pattern_verified(name, node_registry.detect_dynamo_version(status.get("processId")))
            results.append({"name": name, "pattern": True, "result": "FAIL" if problems else "PASS",
                            "reason": "; ".join(problems) or
                            f"{len(inst['nodes'])} 節點 / {len(inst['connectors'])} 連線全部建立"})

        if args.keep:
            # 分組方便目視：正確 create vs. badNames 錯誤示範
            ok_ids = [g for g in good if g in after]
            if ok_ids:
                await bridge.call("create_group", nodeIds=ok_ids, title="registry create（應全部正確）", color="#B9F6CA")
            bad_ids = [g for g in bad_meta if g in after2]
            if bad_ids:
                await bridge.call("create_group", nodeIds=bad_ids, title="badNames 錯誤示範（建出錯的節點）", color="#FFCDD2")
        elif started_empty:
            await bridge.call("clear_workspace")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"executeResponse": r1, "results": results}, f, ensure_ascii=False, indent=2)

    passed = sum(r["result"] == "PASS" for r in results)
    for r in results:
        if r.get("pattern"):
            label = f"[模式] {r['name']}"
        else:
            label = f"{r['name']}" + (f"  [badName: {r['badName']}]" if "badName" in r else f"  -> {r['create']}")
        detail = r.get("reason") or f"in={r.get('inputs')} out={r.get('outputs')}"
        print(f"[{r['result']}] {label}  {detail}")
    print(f"\n{passed}/{len(results)} PASS  (報告: {os.path.relpath(REPORT_PATH, ROOT)})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--allow-nonempty", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args())))
