"""
tools/extract_patterns.py 離線測試（不需 Dynamo）

執行: python -m unittest tests/test_extract_patterns.py -v
"""
import os
import sys
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "bridge", "python"))

import extract_patterns as ep  # noqa: E402
import node_registry  # noqa: E402

DYN = {
    "Nodes": [
        {"ConcreteType": "Dynamo.Graph.Nodes.CodeBlockNodeModel, DynamoCore", "Id": "aaaa0000000000000000000000000001",
         "Code": "\"C:\\\\Users\\\\someone\\\\Desktop\\\\秘密專案A\\\\in.xlsx\";",
         "Inputs": [], "Outputs": [{"Id": "p1"}]},
        {"ConcreteType": "Dynamo.Graph.Nodes.ZeroTouch.DSFunction, DynamoCore", "Id": "bbbb0000000000000000000000000002",
         "FunctionSignature": "Revit.Elements.Element.Geometry", "Inputs": [{"Id": "p2"}], "Outputs": [{"Id": "p3"}]},
        {"ConcreteType": "Dynamo.Graph.Nodes.CustomNodes.Function, DynamoCore", "Id": "cccc0000000000000000000000000003",
         "FunctionSignature": "4d81b7b4-8bc1-4ff8-8fe5-da74bc37fef0", "Inputs": [{"Id": "p4"}], "Outputs": []},
        {"ConcreteType": "CoreNodeModels.Input.ColorPalette, CoreNodeModels", "Id": "dddd0000000000000000000000000004",
         "InputValue": {"R": 255, "G": 140, "B": 0, "A": 255}, "Inputs": [], "Outputs": [{"Id": "p5"}]},
        {"ConcreteType": "Dynamo.Nodes.DSModelElementsSelection, DSRevitNodesUI", "Id": "eeee0000000000000000000000000005",
         "InstanceId": ["12345678-aaaa-bbbb-cccc-1234567890ab-00000001"], "Inputs": [], "Outputs": [{"Id": "p6"}]},
    ],
    "Connectors": [{"Start": "p1", "End": "p2"}, {"Start": "p3", "End": "p4"}],
    "View": {"NodeViews": [{"Id": "bbbb0000000000000000000000000002", "Name": "Element.Geometry", "X": 10, "Y": 20}],
             "Annotations": [{"Title": "群組", "Nodes": ["bbbb0000000000000000000000000002"]}]},
}


class ExtractPatternsTest(unittest.TestCase):
    def test_graph_from_dyn_uses_function_signature_and_ports(self):
        nodes, connectors, groups = ep.graph_from_dyn(DYN)
        by_id = {n["id"][:4]: n for n in nodes}
        self.assertEqual(by_id["bbbb"]["creationName"], "Revit.Elements.Element.Geometry")
        self.assertEqual(by_id["cccc"]["creationName"], "4d81b7b4-8bc1-4ff8-8fe5-da74bc37fef0")
        self.assertEqual(by_id["aaaa"]["creationName"], "Code Block")
        self.assertEqual((by_id["bbbb"]["x"], by_id["bbbb"]["y"]), (10, 20))
        self.assertEqual(len(connectors), 2)
        self.assertEqual(groups[0]["title"], "群組")
        self.assertEqual(len(ep.components(nodes, connectors)[0]), 3)

    def test_redaction_paths_terms_and_unique_ids(self):
        log = []
        terms = ["秘密專案A", "someone"]
        out = ep.redact_text('"C:\\Users\\someone\\Desktop\\秘密專案A\\in.xlsx";', terms, log)
        self.assertEqual(out, f'"{ep.PATH_PLACEHOLDER}";')
        out = ep.redact_text("業主 秘密專案A，元素 12345678-aaaa-bbbb-cccc-1234567890ab-00000001", terms, log)
        self.assertNotIn("秘密專案A", out)
        self.assertNotIn("12345678-aaaa", out)
        self.assertTrue(log)

    def test_custom_node_guid_name_is_kept(self):
        node = {"name": "4d81b7b4-8bc1-4ff8-8fe5-da74bc37fef0", "value": "0e9b0c1a-1111-2222-3333-444444444444"}
        out = ep.redact(node, [], [])
        self.assertEqual(out["name"], node["name"])
        self.assertEqual(out["value"], "<guid>")

    def test_leftovers_detects_remaining_paths_and_terms(self):
        self.assertEqual(ep.leftovers({"v": ep.PATH_PLACEHOLDER}, ["abc"]), [])
        self.assertEqual(ep.leftovers({"v": "D:\\x\\y"}, []), ["Windows 路徑"])
        self.assertEqual(ep.leftovers({"v": "abc"}, ["abc"]), ["abc"])
        self.assertEqual(ep.leftovers({"pythonCode": "for item in items:\n\tpass"}, []), [])

    def test_create_list_input_count_is_captured(self):
        dyn = {"Nodes": [{"ConcreteType": "CoreNodeModels.CreateList, CoreNodeModels", "Id": "ffff",
                          "Inputs": [{"Id": "a"}, {"Id": "b"}], "Outputs": []}]}
        self.assertEqual(node_registry.read_dyn_values(dyn)["ffff"], {"inputCount": 2})

    def test_sensitive_terms_include_file_stem_and_onedrive_org(self):
        terms = ep.sensitive_terms("D:/OneDrive - 某公司 Group/專案資料夾/某專案腳本.dyn")
        for t in ("某專案腳本", "專案資料夾", "OneDrive - 某公司 Group", "某公司 Group"):
            self.assertIn(t, terms)

    def test_color_palette_and_selection_values(self):
        values = node_registry.read_dyn_values(DYN)
        self.assertEqual(values["dddd0000000000000000000000000004"]["value"], "255,140,0,255")
        self.assertNotIn("eeee0000000000000000000000000005", values)  # InstanceId 不會被擷取

    def test_packages_detected_from_dyn_dependencies(self):
        dyn = dict(DYN, NodeLibraryDependencies=[
            {"Name": "Clockwork for Dynamo 2.x", "Version": "2.4.0", "ReferenceType": "Package",
             "Nodes": ["cccc0000000000000000000000000003"]},
            {"Name": "Other", "Version": "1.0", "ReferenceType": "Package", "Nodes": ["ffff0000000000000000000000000009"]},
            {"Name": "pythonnet", "ReferenceType": "NodeModel", "Nodes": ["bbbb0000000000000000000000000002"]}])
        nodes, connectors, _ = ep.graph_from_dyn(dyn)
        ids = [n["id"] for n in nodes if n["id"][:4] in ("bbbb", "cccc")]
        built = node_registry.build_pattern_from_workspace(nodes, connectors, ids, ep.ports_from_dyn(dyn), dyn, {"nodes": {}})
        self.assertEqual(built["packages"], [{"name": "Clockwork for Dynamo 2.x", "version": "2.4.0",
                                              "nodes": ["cccc0000000000000000000000000003"]}])

    def test_package_pattern_places_with_reminder_group(self):
        pattern = {"nodes": [{"ref": "a", "name": "Code Block", "value": "1;"}, {"ref": "b", "name": "pkg-guid"}],
                   "connectors": [{"from": "a", "fromPort": 0, "to": "b", "toPort": 0}],
                   "packages": [{"name": "archi-lab.net", "version": "2024.217.1024", "nodes": ["Materials.Create"]}]}
        inst = node_registry.instantiate_pattern(pattern)
        groups = inst["instructions"]["groups"]
        self.assertEqual(len(groups), 1)
        self.assertIn("archi-lab.net", groups[0]["title"])
        self.assertEqual(sorted(groups[0]["nodeIds"]), sorted(inst["ids"].values()))
        self.assertIn("需安裝外掛", node_registry.format_patterns([("x", pattern, 1)]))
        del pattern["packages"]
        self.assertNotIn("groups", node_registry.instantiate_pattern(pattern)["instructions"])

    def test_save_pattern_keeps_packages(self):
        import shutil, tempfile
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "r.json")
            pk = [{"name": "Genius Loci", "nodes": ["Get DependentElements"]}]
            node_registry.save_pattern("p", {"nodes": [{"id": "1", "name": "Code Block"}]}, path=path,
                                       status="captured", packages=pk)
            self.assertEqual(node_registry.load_registry(path)["patterns"]["p"]["packages"], pk)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # 去重：節點＋Code Block/Python 內容＋連線
    EXCEL = {"nodes": [{"ref": "f", "name": "CoreNodeModels.Input.Filename", "value": "C:/path/to/input.xlsx"},
                       {"ref": "o", "name": "CoreNodeModels.Input.FileObject"},
                       {"ref": "i", "name": "DSOffice.Data.ImportExcel@var,string,bool,bool"},
                       {"ref": "s", "name": "Code Block", "value": "\"Sheet1\";"},
                       {"ref": "r", "name": "DSCore.List.RestOfItems@var[]..[]"},
                       {"ref": "t", "name": "DSCore.List.Transpose@var[]..[]"},
                       {"ref": "c", "name": "Code Block", "value": "L[0];\nL[1];"}],
             "connectors": [{"from": "f", "to": "o"}, {"from": "o", "to": "i"}, {"from": "s", "to": "i", "toPort": 1},
                            {"from": "i", "to": "r"}, {"from": "r", "to": "t"}, {"from": "t", "to": "c"}]}

    def _reg(self, **patterns):
        return {"patterns": patterns}

    def test_real_containment_is_flagged(self):
        level = {"nodes": self.EXCEL["nodes"] + [{"ref": "l", "name": "Revit.Elements.Level.ByElevationAndName@double,string"}],
                 "connectors": self.EXCEL["connectors"] + [{"from": "c", "fromPort": 0, "to": "l", "toPort": 1},
                                                           {"from": "c", "fromPort": 1, "to": "l", "toPort": 0}]}
        rows = ep.check_registry(self._reg(excel=self.EXCEL, level=level))
        self.assertEqual([(a, b, rel) for a, b, _, rel in rows], [("excel", "level", "包含於")])
        # 路徑原值與去識別化後的占位字串視為相同內容
        def with_sheet(value):
            return {"nodes": [dict(n, value=value) if n["ref"] == "s" else n for n in self.EXCEL["nodes"]],
                    "connectors": self.EXCEL["connectors"]}
        masked, raw = with_sheet("\"C:/path/to/input\";"), with_sheet("\"D:\\proj\\a.xlsx\";")
        self.assertEqual(ep.similar_patterns(raw["nodes"], raw["connectors"], self._reg(masked=masked))[0][2], "相同")

    def test_same_node_names_with_different_code_are_not_flagged(self):
        a = {"nodes": [{"ref": "a", "name": "Code Block", "value": "def f(x){return x+1;}"},
                       {"ref": "b", "name": "Code Block", "value": "f(a);"},
                       {"ref": "c", "name": "DSCore.List.Flatten@var[]..[],int"}],
             "connectors": [{"from": "b", "to": "c"}]}
        b = {"nodes": [{"ref": "x", "name": "Code Block", "value": "\"高度\";"}, {"ref": "y", "name": "Code Block", "value": "0;"},
                       {"ref": "z", "name": "DSCore.List.Flatten@var[]..[],int"},
                       {"ref": "w", "name": "Revit.Elements.Element.GetParameterValueByName@string"}],
             "connectors": [{"from": "x", "to": "w", "toPort": 1}, {"from": "w", "to": "z"}]}
        self.assertEqual(ep.check_registry(self._reg(a=a, b=b)), [])

    def test_same_nodes_with_different_connections_are_not_flagged(self):
        get, setp = "Revit.Elements.Element.GetParameterValueByName@string", "Revit.Elements.Element.SetParameterByName@string,var"
        small = {"nodes": [{"ref": "g", "name": get}, {"ref": "s", "name": setp}],
                 "connectors": [{"from": "g", "to": "s", "toPort": 2}]}
        big = {"nodes": [{"ref": "g", "name": get}, {"ref": "s", "name": setp}, {"ref": "t", "name": "Revit.Elements.CeilingType.ByName@string"},
                         {"ref": "m", "name": "DSCore.Math.Round@double"}],
               "connectors": [{"from": "g", "to": "t"}, {"from": "m", "to": "s", "toPort": 2}]}
        self.assertEqual(ep.check_registry(self._reg(small=small, big=big)), [])


if __name__ == "__main__":
    unittest.main()
