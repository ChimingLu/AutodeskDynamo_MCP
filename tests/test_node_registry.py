"""
Node Registry 離線測試（不需 Dynamo、不需 websockets）

執行: python -m unittest tests/test_node_registry.py -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "bridge", "python"))

import node_registry  # noqa: E402

SEED = os.path.join(ROOT, "domain", "node_registry.json")
G1 = "11111111-1111-1111-1111-111111111111"
G2 = "22222222-2222-2222-2222-222222222222"
G3 = "33333333-3333-3333-3333-333333333333"


class GetNodeRecipeTest(unittest.TestCase):
    def test_seed_is_valid_json(self):
        reg = node_registry.load_registry(SEED)
        self.assertTrue(reg["globalRules"])
        self.assertIn("String", reg["nodes"])

    def test_case_insensitive_batch_lookup(self):
        res = node_registry.lookup_recipes(["list.filterbyboolmask", "ELEMENT.NAME"], path=SEED)
        names = [f["name"] for f in res["found"]]
        self.assertEqual(names, ["List.FilterByBoolMask", "Element.Name"])
        self.assertEqual(res["found"][0]["inputs"], ["list", "mask"])
        self.assertEqual(res["missing"], [])

    def test_bad_name_returns_correct_create_with_warning(self):
        res = node_registry.lookup_recipes(["Core.Input.Boolean", "String"], path=SEED)
        boolean, string = res["found"]
        self.assertEqual(boolean["name"], "Boolean")
        self.assertEqual(boolean["create"], "CoreNodeModels.Input.BoolSelector")
        self.assertIn("warning", boolean)
        self.assertEqual(string["create"], "CoreNodeModels.Input.StringInput")
        self.assertIn("warning", string)

    def test_full_name_and_signature_forms_match(self):
        res = node_registry.lookup_recipes(
            ["DSCoreNodes.DSCore.String.Split", "String.Contains@string,string,bool"], path=SEED)
        self.assertEqual([f["create"] for f in res["found"]], ["String.Split", "String.Contains"])

    def test_unknown_names_reported_as_missing(self):
        res = node_registry.lookup_recipes(["Totally.Unknown", "List.Coun"], path=SEED)
        self.assertEqual(res["found"], [])
        self.assertEqual([m["query"] for m in res["missing"]], ["Totally.Unknown", "List.Coun"])
        self.assertIn("List.Count", res["missing"][1]["didYouMean"])
        text = node_registry.format_recipes(res)
        self.assertIn("search_nodes", text)

    def test_global_rules_once_and_optional(self):
        text = node_registry.format_recipes(node_registry.lookup_recipes(["Watch", "Or"], path=SEED))
        self.assertEqual(text.count("## 全域規則"), 1)
        res = node_registry.lookup_recipes(["Watch"], path=SEED, include_rules=False)
        self.assertEqual(res["globalRules"], [])

    def test_resolve_create_name_for_search_results(self):
        reg = node_registry.load_registry(SEED)
        # 在 registry 中 -> 用已驗證 create
        self.assertEqual(
            node_registry.resolve_create_name("Split", "DSCoreNodes.DSCore.String.Split",
                                              "DSCore.String.Split@string,string[]", reg),
            ("String.Split", "registry"))
        # 不在 registry、有 mangled creationName -> creationName
        self.assertEqual(
            node_registry.resolve_create_name("Pad", "DSCoreNodes.DSCore.Fake.Pad",
                                              "DSCore.Fake.Pad@string,int", reg),
            ("DSCore.Fake.Pad@string,int", "creationName"))
        # creationName 等於 fullName -> 取最後兩段
        self.assertEqual(
            node_registry.resolve_create_name("Pad", "DSCoreNodes.DSCore.Fake.Pad",
                                              "DSCoreNodes.DSCore.Fake.Pad", reg),
            ("Fake.Pad", "short"))

    def test_correct_instruction_names(self):
        nodes = [{"id": G1, "name": "Boolean"}, {"id": G2, "name": "List.Count"}]
        corrections = node_registry.correct_instruction_names(nodes, path=SEED)
        self.assertEqual(nodes[0]["name"], "CoreNodeModels.Input.BoolSelector")
        self.assertEqual(nodes[1]["name"], "List.Count")
        self.assertEqual(len(corrections), 1)


class AutoLearnTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "node_registry.json")
        shutil.copy(SEED, self.path)
        self.original_room_name = node_registry.load_registry(self.path)["nodes"]["Room.Name"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_learn_new_node_and_bad_name(self):
        sent = [
            {"id": G1, "name": "Fake.Join"},            # 新建成功 -> auto-verified
            {"id": G2, "name": "List.Flattn"},          # 沒建出來 -> badNames
            {"id": G3, "name": "Revit.Elements.Room.Name"},  # 人工驗證 -> 不覆寫
            {"id": "not-a-guid", "name": "Watch"},      # 非 GUID -> 略過
        ]
        graph = [
            {"id": G1, "name": "Fake.Join", "creationName": "DSCore.Fake.Join@string,string[]"},
            {"id": G3, "name": "Room.Name", "creationName": "Revit.Elements.Room.Name"},
        ]
        structured = [
            {"id": G1, "inputs": [{"name": "separator"}, {"name": "strings"}], "outputs": [{"name": "str"}]},
            {"id": G3, "inputs": [{"name": "X"}], "outputs": [{"name": "Y"}]},
        ]
        report = node_registry.learn_from_execution(
            sent, set(), graph, structured, dynamo_version="Dynamo 2.6", path=self.path)
        self.assertEqual(report["learned"], ["Fake.Join"])
        self.assertEqual(report["badNames"], ["List.Flattn"])

        reg = node_registry.load_registry(self.path)
        learned = reg["nodes"]["Fake.Join"]
        self.assertEqual(learned["status"], node_registry.AUTO_STATUS)
        self.assertEqual(learned["create"], "Fake.Join")
        self.assertEqual(learned["inputs"], ["separator", "strings"])
        self.assertEqual(learned["outputs"], ["str"])
        self.assertTrue(learned["verified"].startswith("Dynamo 2.6"))
        self.assertIsNone(reg["nodes"]["List.Flattn"]["create"])
        self.assertEqual(reg["nodes"]["Room.Name"], self.original_room_name)

        # 寫回的檔案仍可由 get_node_recipe 查到
        res = node_registry.lookup_recipes(["fake.join", "List.Flattn"], path=self.path)
        self.assertEqual([f["name"] for f in res["found"]], ["Fake.Join", "List.Flattn"])

    def test_failed_alias_added_to_existing_entry_badnames(self):
        sent = [{"id": G1, "name": "Core.Input.String"}, {"id": G2, "name": "Element.Name"}]
        errors = [f"[CreateNode Failed] Element.Name (ID: {G2}): boom"]
        graph = [{"id": G2, "name": "Element.Name"}]
        node_registry.learn_from_execution(sent, set(), graph, [], errors=errors, path=self.path)
        reg = node_registry.load_registry(self.path)
        # Core.Input.String 已在 badNames，不重複
        self.assertEqual(reg["nodes"]["String"]["badNames"].count("Core.Input.String"), 1)
        # 失敗的是 registry 的 create 名稱本身 -> 不改人工項目
        self.assertNotIn("badNames", reg["nodes"]["Element.Name"])

    def test_pre_existing_nodes_are_not_learned(self):
        sent = [{"id": G1, "name": "Sloppy.Name"}]
        graph = [{"id": G1, "name": "X"}]
        report = node_registry.learn_from_execution(sent, {G1.upper()}, graph, [], path=self.path)
        self.assertEqual(report["learned"], [])
        self.assertNotIn("Sloppy.Name", node_registry.load_registry(self.path)["nodes"])

    def test_auto_failed_entry_recovers_on_success(self):
        node_registry.learn_from_execution([{"id": G1, "name": "Pkg.Node"}], set(), [], [], path=self.path)
        node_registry.learn_from_execution(
            [{"id": G2, "name": "Pkg.Node"}], set(), [{"id": G2, "name": "Node"}],
            [{"id": G2, "inputs": [], "outputs": [{"name": "out"}]}], path=self.path)
        entry = node_registry.load_registry(self.path)["nodes"]["Pkg.Node"]
        self.assertEqual(entry["status"], node_registry.AUTO_STATUS)
        self.assertEqual(entry["create"], "Pkg.Node")
        self.assertNotIn("badNames", entry)
        self.assertNotIn("gotchas", entry)

    def test_write_is_atomic_and_stable(self):
        reg = node_registry.load_registry(self.path)
        node_registry.save_registry(reg, self.path)
        with open(self.path, encoding="utf-8") as f:
            first = f.read()
        self.assertEqual(json.loads(first), reg)
        node_registry.save_registry(node_registry.load_registry(self.path), self.path)
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(f.read(), first)
        self.assertEqual([n for n in os.listdir(self.tmp) if n.endswith(".tmp")], [])


class AmbiguityAndSearchTest(unittest.TestCase):
    def test_same_name_resolution_is_not_learned(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "r.json")
            shutil.copy(SEED, path)
            report = node_registry.learn_from_execution(
                [{"id": G1, "name": "Sheets"}], set(),
                [{"id": G1, "name": "Sheet.Sheets", "creationName": "Revit.Elements.Views.Sheet.Sheets"}], [], path=path)
            self.assertEqual(report["learned"], [])
            self.assertEqual(report["ambiguous"][0]["name"], "Sheets")
            entry = node_registry.load_registry(path)["nodes"]["Sheets"]
            self.assertIsNone(entry["create"])
            self.assertIn("Sheet.Sheets", entry["gotchas"][0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_name_matches_node(self):
        m = node_registry.name_matches_node
        self.assertTrue(m("List.Count", {"name": "List.Count", "creationName": "DSCore.List.Count@var[]..[]"}))
        self.assertTrue(m("Revit.Elements.Room.Name", {"name": "Room.Name"}))
        self.assertTrue(m("CoreNodeModels.Input.StringInput", {"name": "String", "fullName": "CoreNodeModels.Input.StringInput"}))
        self.assertFalse(m("String", {"name": "FloatFormatHandling.String",
                                      "creationName": "Newtonsoft.Json.FloatFormatHandling.String"}))
        self.assertFalse(m("Views", {"name": "Sheet.Views", "creationName": "Revit.Elements.Views.Sheet.Views"}))

    def test_ui_nodes_use_display_name_in_search(self):
        reg = node_registry.load_registry(SEED)
        r = node_registry.resolve_create_name
        self.assertEqual(r("All Elements of Category in View", "Selection.All Elements of Category in View",
                           "Selection.All Elements of Category in View", reg, element_type="NodeModelSearchElement")[0],
                         "All Elements of Category in View")
        self.assertEqual(r("Views", "Selection.Views", "Selection.Views", reg, element_type="NodeModelSearchElement"),
                         ("DSRevitNodesUI.Views", "registry"))


class PatternTest(unittest.TestCase):
    QUERY = "選擇品類，取得視圖中該品類的所有元件"

    def test_chinese_query_finds_category_in_view_patterns(self):
        names = [m[0] for m in node_registry.search_patterns(self.QUERY, path=SEED)]
        self.assertTrue(any("視圖中該品類的所有元件" in n for n in names))

    def test_instantiate_uses_fresh_guids_and_maps_connectors(self):
        name, pattern, _ = node_registry.search_patterns(self.QUERY, path=SEED)[0]
        a = node_registry.instantiate_pattern(pattern, 100, 50)
        b = node_registry.instantiate_pattern(pattern)
        ids = {n["id"] for n in a["instructions"]["nodes"]}
        self.assertTrue(all(node_registry.is_guid(i) for i in ids))
        self.assertFalse(ids & {n["id"] for n in b["instructions"]["nodes"]})
        self.assertEqual(len(a["instructions"]["connectors"]), len(pattern["connectors"]))
        for c in a["instructions"]["connectors"]:
            self.assertIn(c["from"], ids)
            self.assertIn(c["to"], ids)
        self.assertEqual(min(n["x"] for n in a["instructions"]["nodes"]), 100)

    def test_save_roundtrip_and_graph_check(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "r.json")
            shutil.copy(SEED, path)
            inst = {"nodes": [{"id": G1, "name": "Document.Current", "x": 500, "y": 300},
                              {"id": G2, "name": "Document.ActiveView", "x": 750, "y": 300}],
                    "connectors": [{"from": G1, "fromPort": 0, "to": G2, "toPort": 0}]}
            graph_nodes = [{"id": G1}, {"id": G2}]
            self.assertEqual(node_registry.check_pattern_in_graph(inst, graph_nodes, []),
                             [f"連線不在工作區: {G1}[0] → {G2}[0]"])
            problems = node_registry.check_pattern_in_graph(
                inst, graph_nodes, [{"from": G1, "fromPort": 0, "to": G2, "toPort": 0}])
            res = node_registry.save_pattern("目前視圖", inst, "取得作用中視圖", ["視圖"], problems=problems,
                                             dynamo_version="Dynamo 2.6", path=path)
            self.assertEqual(res["patternStatus"], "verified")
            saved = node_registry.load_registry(path)["patterns"]["目前視圖"]
            self.assertEqual([n["x"] for n in saved["nodes"]], [0, 250])
            self.assertEqual(saved["connectors"], [{"from": "document_current", "fromPort": 0,
                                                    "to": "document_activeview", "toPort": 0}])
            self.assertEqual(node_registry.save_pattern("目前視圖", inst, path=path)["status"], "error")
            # get_node_recipe 會列出用到這些節點的模式
            res = node_registry.lookup_recipes(["Document.ActiveView"], path=path)
            self.assertIn("目前視圖", res["relatedPatterns"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CaptureFromWorkspaceTest(unittest.TestCase):
    # 模擬 get_graph_status / get_nodes_structured / .dyn 的實際欄位
    GRAPH = [
        {"id": G1, "name": "String", "fullName": "CoreNodeModels.Input.StringInput", "creationName": "", "x": 100, "y": 100},
        {"id": G2, "name": "Category.ByName", "fullName": "Dynamo.Graph.Nodes.ZeroTouch.DSFunction",
         "creationName": "Revit.Elements.Category.ByName@string", "x": 350, "y": 100},
        {"id": G3, "name": "String.Join", "fullName": "Dynamo.Graph.Nodes.ZeroTouch.DSVarArgFunction",
         "creationName": "DSCore.String.Join@string,string[]", "x": 600, "y": 100},
        {"id": "44444444-4444-4444-4444-444444444444", "name": "Element Types",
         "fullName": "DSRevitNodesUI.ElementTypes", "creationName": "", "x": 0, "y": 0},
        {"id": "55555555-5555-5555-5555-555555555555", "name": "Watch", "fullName": "CoreNodeModels.Watch",
         "creationName": "", "x": 900, "y": 100},
    ]
    CONNECTORS = [
        {"from": G1, "fromPort": 0, "to": G2, "toPort": 0},
        {"from": G2, "fromPort": 0, "to": G3, "toPort": 1},
        {"from": G3, "fromPort": 0, "to": "55555555-5555-5555-5555-555555555555", "toPort": 0},
    ]
    DYN = {"Nodes": [{"ConcreteType": "CoreNodeModels.Input.StringInput, CoreNodeModels",
                      "Id": G1.replace("-", ""), "InputValue": "OST_Walls"}]}

    def test_choose_create_names(self):
        reg = node_registry.load_registry(SEED)
        c = lambda g: node_registry.choose_create_name(g, reg)
        self.assertEqual(c(self.GRAPH[0]), ("CoreNodeModels.Input.StringInput", "registry"))
        self.assertEqual(c(self.GRAPH[1]), ("Category.ByName", "registry"))
        self.assertEqual(c(self.GRAPH[3]), ("DSRevitNodesUI.ElementTypes", "className"))
        self.assertEqual(c({"id": G1, "name": "Views", "fullName": "DSRevitNodesUI.Views", "creationName": ""}),
                         ("DSRevitNodesUI.Views", "registry"))
        self.assertEqual(c({"id": G1, "name": "Foo", "fullName": "Dynamo.Graph.Nodes.ZeroTouch.DSFunction",
                            "creationName": "Pkg.Foo@int"}), ("Pkg.Foo@int", "creationName"))

    def test_build_pattern_from_selection_with_dyn_values(self):
        reg = node_registry.load_registry(SEED)
        built = node_registry.build_pattern_from_workspace(self.GRAPH, self.CONNECTORS, [G1, G2, G3], [], self.DYN, reg)
        nodes = {n["id"]: n for n in built["instructions"]["nodes"]}
        self.assertEqual(set(nodes), {G1, G2, G3})
        self.assertEqual(nodes[G1]["value"], "OST_Walls")
        self.assertEqual(len(built["instructions"]["connectors"]), 2)  # 到 Watch 的連線在選取範圍外
        self.assertEqual(built["externalInputs"], [])
        self.assertEqual(built["sources"][G3], "registry")  # String.Join 已 auto-verified

    def test_missing_values_and_external_inputs_are_reported(self):
        reg = node_registry.load_registry(SEED)
        built = node_registry.build_pattern_from_workspace(self.GRAPH, self.CONNECTORS, [G2, G3], [], None, reg)
        self.assertEqual(built["externalInputs"], ["Category.ByName[0] ← String（模式外的節點）"])
        built = node_registry.build_pattern_from_workspace(self.GRAPH, self.CONNECTORS, [G1], [], None, reg)
        self.assertIn("note", built["instructions"]["nodes"][0])
        self.assertTrue(built["warnings"])

    def test_capture_saved_as_captured_then_marked_verified(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "r.json")
            shutil.copy(SEED, path)
            reg = node_registry.load_registry(path)
            built = node_registry.build_pattern_from_workspace(self.GRAPH, self.CONNECTORS, [G1, G2], [], self.DYN, reg)
            node_registry.save_pattern("OST品類", built["instructions"], "x", ["品類"], path=path, status="captured")
            p = node_registry.load_registry(path)["patterns"]["OST品類"]
            self.assertEqual(p["status"], "captured")
            self.assertNotIn("verified", p)
            self.assertEqual(p["nodes"][0]["value"], "OST_Walls")
            self.assertEqual([n["x"] for n in p["nodes"]], [0, 250])
            inst = node_registry.instantiate_pattern(p)["instructions"]
            self.assertEqual(inst["nodes"][0]["value"], "OST_Walls")
            self.assertTrue(node_registry.mark_pattern_verified("OST品類", "Dynamo 2.6", path=path))
            self.assertEqual(node_registry.load_registry(path)["patterns"]["OST品類"]["status"], "verified")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
