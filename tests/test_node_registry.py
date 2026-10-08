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


if __name__ == "__main__":
    unittest.main()
