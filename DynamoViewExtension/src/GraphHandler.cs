using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Dynamo.Graph.Nodes;
using Dynamo.Graph.Connectors;
using Dynamo.Models;
using Dynamo.ViewModels;
using Dynamo.Search;
using Dynamo.Search.SearchElements;
using Dynamo.Graph.Nodes.CustomNodes;

namespace DynamoMCPListener
{
    [Autodesk.DesignScript.Runtime.IsVisibleInDynamoLibrary(false)]
    public class GraphHandler
    {
        private DynamoViewModel _vm;
        private DynamoModel _dynamoModel;
        private JArray _commonNodesCache;
        private string _sessionId;
        private Dictionary<string, Guid> _nodeIdMap; // 字串 ID -> Dynamo GUID 映射表

        public GraphHandler(DynamoViewModel vm, string sessionId)
        {
            _vm = vm;
            _dynamoModel = vm.Model;
            _sessionId = sessionId;
            _nodeIdMap = new Dictionary<string, Guid>();
        }

        public string HandleCommand(string jsonLine)
        {
            try
            {
                var data = JObject.Parse(jsonLine);
                var errors = new List<string>();

                // 0. Handle Actions (like clear_graph)
                string action = data["action"]?.ToString();
                if (action == "clear_graph")
                {
                    // This must be run on UI thread, handled by WebSocketClient dispatcher
                    var nodesToDelete = _dynamoModel.CurrentWorkspace.Nodes.Select(n => n.GUID).ToList();
                    if (nodesToDelete.Any())
                    {
                        _dynamoModel.ExecuteCommand(new DynamoModel.DeleteModelCommand(nodesToDelete));
                    }
                    _nodeIdMap.Clear();
                    MCPLogger.Info("[GraphHandler] Workspace cleared via DeleteModelCommand.");
                    return "{\"status\": \"ok\", \"message\": \"Workspace cleared\"}";
                }

                if (action == "get_graph_status")
                {
                    var nodes = _dynamoModel.CurrentWorkspace.Nodes.Select(n => new
                    {
                        id = n.GUID.ToString(),
                        name = n.Name,
                        fullName = n.GetType().FullName,
                        creationName = n.GetType().GetProperty("CreationName")?.GetValue(n)?.ToString() ?? n.Name,
                        x = n.X,
                        y = n.Y
                    }).ToList();

                    var connectors = _dynamoModel.CurrentWorkspace.Connectors.Select(c => new
                    {
                        from = c.Start.Owner.GUID.ToString(),
                        to = c.End.Owner.GUID.ToString(),
                        fromPort = c.Start.Index,
                        toPort = c.End.Index
                    }).ToList();

                    var statusData = new
                    {
                        sessionId = _sessionId,
                        processId = System.Diagnostics.Process.GetCurrentProcess().Id,
                        workspace = new {
                            name = _dynamoModel.CurrentWorkspace.Name,
                            fileName = _dynamoModel.CurrentWorkspace.FileName
                        },
                        nodeCount = nodes.Count,
                        connectorCount = connectors.Count,
                        nodes = nodes,
                        connectors = connectors
                    };

                    return JsonConvert.SerializeObject(statusData);
                }
                
                // === MCP Resources Layer: Structured Data Queries ===
                if (action == "get_nodes_structured")
                {
                    var nodes = _dynamoModel.CurrentWorkspace.Nodes.Select(n => {
                        string stateStr = "Active";
                        try { stateStr = n.State.ToString(); } catch { }
                        return new
                        {
                            id = n.GUID.ToString(),
                            name = n.Name,
                            fullName = n.GetType().FullName,
                            x = n.X,
                            y = n.Y,
                            state = stateStr,
                            isSelected = n.IsSelected,
                            inputs = n.InPorts.Select(p => new
                            {
                                name = p.Name,
                                type = p.PortType.ToString(),
                                isConnected = p.IsConnected
                            }).ToList(),
                            outputs = n.OutPorts.Select(p => new
                            {
                                name = p.Name,
                                type = p.PortType.ToString()
                            }).ToList(),
                            errorMessage = stateStr.Contains("Error") ? stateStr : null
                        };
                    }).ToList();

                    return JsonConvert.SerializeObject(new { status = "ok", nodes = nodes });
                }

                if (action == "get_connectors_structured")
                {
                    var connectors = _dynamoModel.CurrentWorkspace.Connectors.Select(c => new
                    {
                        from = c.Start.Owner.GUID.ToString(),
                        to = c.End.Owner.GUID.ToString(),
                        fromPort = c.Start.Index,
                        toPort = c.End.Index,
                        fromPortName = c.Start.Name,
                        toPortName = c.End.Name
                    }).ToList();

                    return JsonConvert.SerializeObject(new { status = "ok", connectors = connectors });
                }

                if (action == "get_selection")
                {
                    var selected = _dynamoModel.CurrentWorkspace.Nodes
                        .Where(n => n.IsSelected)
                        .Select(n => new
                        {
                            id = n.GUID.ToString(),
                            name = n.Name,
                            x = n.X,
                            y = n.Y
                        }).ToList();

                    return JsonConvert.SerializeObject(new { status = "ok", count = selected.Count, nodes = selected });
                }

                if (action == "get_error_nodes")
                {
                    var errorNodes = _dynamoModel.CurrentWorkspace.Nodes
                        .Where(n => {
                            try {
                                string s = n.State.ToString();
                                return s.Contains("Error") || s.Contains("Warning");
                            } catch { return false; }
                        })
                        .Select(n => {
                            string stateStr = "Unknown";
                            try { stateStr = n.State.ToString(); } catch { }
                            return new
                            {
                                id = n.GUID.ToString(),
                                name = n.Name,
                                state = stateStr,
                                errorMessage = stateStr
                            };
                        }).ToList();

                    return JsonConvert.SerializeObject(new { status = "ok", count = errorNodes.Count, nodes = errorNodes });
                }

                if (action == "get_node_details")
                {
                    string targetId = data["nodeId"]?.ToString();
                    if (string.IsNullOrEmpty(targetId))
                    {
                        return "{\"status\": \"error\", \"message\": \"Missing nodeId parameter\"}";
                    }

                    Guid targetGuid;
                    if (!Guid.TryParse(targetId, out targetGuid))
                    {
                        // 嘗試從 ID 映射表查找
                        if (!_nodeIdMap.TryGetValue(targetId, out targetGuid))
                        {
                            return "{\"status\": \"error\", \"message\": \"Node not found\"}";
                        }
                    }

                    var node = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(n => n.GUID == targetGuid);
                    if (node == null)
                    {
                        return "{\"status\": \"error\", \"message\": \"Node not found\"}";
                    }

                    string nodeStateStr = "Active";
                    try { nodeStateStr = node.State.ToString(); } catch { }

                    var nodeDetail = new
                    {
                        id = node.GUID.ToString(),
                        name = node.Name,
                        fullName = node.GetType().FullName,
                        x = node.X,
                        y = node.Y,
                        state = nodeStateStr,
                        isSelected = node.IsSelected,
                        inputs = node.InPorts.Select(p => new
                        {
                            name = p.Name,
                            type = p.PortType.ToString(),
                            isConnected = p.IsConnected,
                            connectedFrom = p.IsConnected ? _dynamoModel.CurrentWorkspace.Connectors
                                .Where(c => c.End.Owner.GUID == node.GUID && c.End.Index == p.Index)
                                .Select(c => c.Start.Owner.GUID.ToString())
                                .FirstOrDefault() : null
                        }).ToList(),
                        outputs = node.OutPorts.Select(p => new
                        {
                            name = p.Name,
                            type = p.PortType.ToString(),
                            connectedTo = _dynamoModel.CurrentWorkspace.Connectors
                                .Where(c => c.Start.Owner.GUID == node.GUID && c.Start.Index == p.Index)
                                .Select(c => c.End.Owner.GUID.ToString())
                                .ToList()
                        }).ToList(),
                        errorMessage = nodeStateStr.Contains("Error") ? nodeStateStr : null
                    };

                    return JsonConvert.SerializeObject(new { status = "ok", node = nodeDetail });
                }

                if (action == "list_nodes") {
                    string filter = data["filter"]?.ToString()?.ToLower() ?? "";
                    MCPLogger.Info($"[list_nodes] Searching for: {filter}");

                    // Ultimate recursive search for SearchModel/SearchViewModel
                    string diagPath = MCPConfig.DIAG_FILE_PATH;
                    string diagDir = System.IO.Path.GetDirectoryName(diagPath);
                    if (!System.IO.Directory.Exists(diagDir)) System.IO.Directory.CreateDirectory(diagDir);
                    object searchModel = null;
                    
                    try {
                        List<string> diagLines = new List<string>();
                        diagLines.Add($"--- Deep Search Start ---");

                        // Helper to find a search-related object in any instance
                        Func<object, string, object> findSearchObj = (obj, label) => {
                            if (obj == null) return null;
                            var type = obj.GetType();
                            diagLines.Add($"Scanning {label} ({type.Name})...");
                            
                            // Check Properties
                            foreach (var p in type.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                                try {
                                    if (p.Name.Contains("Search") || p.PropertyType.Name.Contains("Search")) {
                                        var val = p.GetValue(obj);
                                        diagLines.Add($"  Prop Match: {p.Name} (Type: {p.PropertyType.Name}) -> {(val != null ? "FOUND" : "null")}");
                                        if (val != null && (p.PropertyType.Name.Contains("SearchModel") || p.Name.Contains("SearchModel"))) return val;
                                        if (val != null && (p.PropertyType.Name.Contains("SearchViewModel") || p.Name.Contains("SearchViewModel"))) {
                                            // Try to get Model from ViewModel
                                            var mProp = val.GetType().GetProperty("Model", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                                            var mVal = mProp?.GetValue(val);
                                            if (mVal != null) return mVal;
                                        }
                                    }
                                } catch {}
                            }
                            
                            // Check Fields
                            foreach (var f in type.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                                try {
                                    if (f.Name.Contains("Search") || f.FieldType.Name.Contains("Search")) {
                                        var val = f.GetValue(obj);
                                        diagLines.Add($"  Field Match: {f.Name} (Type: {f.FieldType.Name}) -> {(val != null ? "FOUND" : "null")}");
                                        if (val != null && (f.FieldType.Name.Contains("SearchModel") || f.Name.Contains("SearchModel"))) return val;
                                    }
                                } catch {}
                            }
                            return null;
                        };

                        searchModel = findSearchObj(_vm.Model, "Model") ?? findSearchObj(_vm, "VM");
                        System.IO.File.WriteAllLines(diagPath, diagLines);
                    } catch (Exception ex) {
                        System.IO.File.AppendAllText(diagPath, "Fatal Diag Error: " + ex.ToString());
                    }

                    if (searchModel == null)
                    {
                        return "{\"status\": \"error\", \"message\": \"SearchModel could not be located even with deep scan. Check props_diag.txt for clues.\"}";
                    }

                    // Diagnostic: Scan ALL members of NodeSearchModel since standard names failed
                    try {
                        List<string> scanLines = new List<string>();
                        scanLines.Add($"--- Scanning NodeSearchModel ({searchModel.GetType().FullName}) ---");
                        
                        foreach (var p in searchModel.GetType().GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                            try { scanLines.Add($"  Prop: {p.Name} (Type: {p.PropertyType.Name})"); } catch {}
                        }
                        foreach (var f in searchModel.GetType().GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                            try { scanLines.Add($"  Field: {f.Name} (Type: {f.FieldType.Name})"); } catch {}
                        }
                        System.IO.File.AppendAllLines(diagPath, scanLines);
                    } catch {}

                    // Target logic: Dynamic find collection
                    IEnumerable<NodeSearchElement> elements = null;
                    
                    // Try to find ANY member that is IEnumerable<NodeSearchElement>
                    foreach (var p in searchModel.GetType().GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                    {
                        if (typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(p.PropertyType))
                        {
                            try { elements = p.GetValue(searchModel) as IEnumerable<NodeSearchElement>; } catch {}
                            if (elements != null) break;
                        }
                    }

                    if (elements == null)
                    {
                        foreach (var f in searchModel.GetType().GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                        {
                            if (typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(f.FieldType))
                            {
                                try { elements = f.GetValue(searchModel) as IEnumerable<NodeSearchElement>; } catch {}
                                if (elements != null) break;
                            }
                        }
                    }

                    if (elements == null)
                    {
                        return $"{{\"status\": \"error\", \"message\": \"Could not find nodes collection in {searchModel.GetType().Name}. Check props_diag.txt for potential candidates.\"}}";
                    }

                    var results = elements
                        .Where(el => string.IsNullOrEmpty(filter) || 
                                     el.Name.ToLower().Contains(filter) || 
                                     el.FullName.ToLower().Contains(filter))
                        .Take(50)
                        .Select(el => {
                            // Deep extraction of the real IDENTIFIER for creation
                            string cName = el.FullName;
                            try {
                                var entryProp = el.GetType().GetProperty("Entry", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                                var entry = entryProp?.GetValue(el);
                                if (entry != null) {
                                    var cNameProp = entry.GetType().GetProperty("CreationName", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                                    var val = cNameProp?.GetValue(entry)?.ToString();
                                    if (!string.IsNullOrEmpty(val)) cName = val;
                                }
                            } catch {}

                            return new {
                                name = el.Name,
                                fullName = el.FullName,
                                creationName = cName,
                                description = el.Description,
                                type = el.GetType().Name
                            };
                        }).ToList();

                    // Format display result for AI awareness
                    var displayLines = new List<string> { $"🔍 搜尋 '{filter}' 找到 {results.Count} 個結果 (僅列出前 50 個):\n" };
                    foreach (var n in results) {
                        displayLines.Add($"- **{n.name}**");
                        displayLines.Add($"  fullName: `{n.fullName}`");
                        displayLines.Add($"  creationName: `{n.creationName}`");
                        if (!string.IsNullOrEmpty(n.description)) displayLines.Add($"  說明: {n.description}");
                        displayLines.Add("");
                    }

                    return JsonConvert.SerializeObject(new { 
                        status = "ok", 
                        count = results.Count,
                        nodes = results,
                        display = string.Join("\n", displayLines)
                    });
                }
                
                // 1. Create Nodes
                if (data["nodes"] != null)
                {
                    foreach (var n in data["nodes"])
                    {
                        try 
                        {
                            CreateNode(n);
                        }
                        catch (Exception ex)
                        {
                            string nodeName = n["name"]?.ToString();
                            string msg = $"[CreateNode Failed] {nodeName} (ID: {n["id"]}): {ex.Message}";
                            MCPLogger.Error($"Critical Failure creating node '{nodeName}':", ex);
                            errors.Add(msg);
                        }
                    }
                }

                // 2. Create Connectors
                if (data["connectors"] != null)
                {
                    foreach (var c in data["connectors"])
                    {
                        try
                        {
                            CreateConnection(c);
                        }
                        catch (Exception ex)
                        {
                            string msg = $"[CreateConnection Failed] {c["from"]}->{c["to"]}: {ex.Message}";
                            MCPLogger.Error(msg, ex);
                            errors.Add(msg);
                        }
                    }
                }

                if (errors.Any())
                {
                    return JsonConvert.SerializeObject(new { status = "error", message = "Partial failure", errors = errors });
                }

                return "{\"status\": \"ok\"}";
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"Error executing instructions: {ex.Message}");
                return JsonConvert.SerializeObject(new { status = "error", message = ex.Message });
            }
        }

        private void CreateNode(JToken n)
        {
            string nodeName = n["name"]?.ToString();
            string nodeIdStr = n["id"]?.ToString();
            string creationNameOverride = n["creationName"]?.ToString();
            double x = n["x"]?.ToObject<double>() ?? 0;
            double y = n["y"]?.ToObject<double>() ?? 0;

            MCPLogger.Info($"[CreateNode] Processing Node: {nodeName} (ID: {nodeIdStr})");

            Guid dynamoGuid = Guid.TryParse(nodeIdStr, out Guid parsedGuid) ? parsedGuid : Guid.NewGuid();
            if (!string.IsNullOrEmpty(nodeIdStr))
            {
                _nodeIdMap[nodeIdStr] = dynamoGuid;
            }

            // === 0. CHECK EXISTENCE (The Fix) ===
            var existingNode = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(nd => nd.GUID == dynamoGuid);
            if (existingNode != null)
            {
                // [UPDATE MODE] Node exists, just update position and values
                MCPLogger.Info($"[Upsert] Node {dynamoGuid} exists. Updating properties only.");
                
                // Update Position
                var updatePosCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, "Position", $"{x},{y}");
                _dynamoModel.ExecuteCommand(updatePosCmd);

                // Update Values (Code Block / SetValue)
                if (n["value"] != null)
                {
                    string val = n["value"].ToString();
                    if (nodeName == "Code Block" && !val.EndsWith(";")) val += ";";

                    string propName = "Value";
                    if (nodeName == "Code Block") propName = "Code";
                    else 
                    {
                        // Dynamic property resolution
                        string resolvedProp = GetValuePropertyName(existingNode.CreationName) ?? "Value";
                        propName = resolvedProp;
                    }

                    var updateValCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, propName, val);
                    _dynamoModel.ExecuteCommand(updateValCmd);
                }

                // Update Python Script (Special Handling)
                if (nodeName == "Python Script" || nodeName.Contains("PythonScript"))
                {
                    string code = n["script"]?.ToString() ?? n["pythonCode"]?.ToString();
                    if (code != null)
                    {
                        UpdatePythonCode(existingNode, code);
                    }
                }

                HandlePreview(n, dynamoGuid);
                return; // Exit, do NOT create new node
            }

            // === 1. CREATE MODE (Node does not exist) ===
            
            // ... (Special handling for Code Block / Python Script creation) ...
            if (nodeName == "Number" || nodeName == "Code Block")
            {
                var cmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, "Code Block", x, y, false, false);
                _dynamoModel.ExecuteCommand(cmd);
                
                if (n["value"] != null)
                {
                    string val = n["value"].ToString();
                    if (!val.EndsWith(";")) val += ";";
                    var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, "Code", val);
                    _dynamoModel.ExecuteCommand(updateCmd);
                }
                
                HandlePreview(n, dynamoGuid);
                return;
            }

            if (nodeName == "Python Script" || nodeName.Contains("PythonScript"))
            {
                // Try multiple names for Python Script
                string[] possibleNames = { "Python Script", "Core.Scripting.Python Script", "PythonScript" };
                bool created = false;
                foreach (var nameToTry in possibleNames) {
                    try {
                        _dynamoModel.ExecuteCommand(new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, nameToTry, x, y, false, false));
                        if (_dynamoModel.CurrentWorkspace.Nodes.Any(nd => nd.GUID == dynamoGuid)) {
                            created = true;
                            break;
                        }
                    } catch {}
                }

                if (created)
                {
                    var node = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(nd => nd.GUID == dynamoGuid);
                    
                    // Input Count Adjustment
                    if (node != null && n["inputCount"] != null)
                    {
                        AdjustInputPorts(node, n["inputCount"].ToObject<int>());
                    }

                    // Python Code Injection
                    string code = n["script"]?.ToString() ?? n["pythonCode"]?.ToString();
                    if (code != null && node != null)
                    {
                         UpdatePythonCode(node, code);
                    }
                }
                HandlePreview(n, dynamoGuid);
                return;
            }

            // Standard Node Creation
            string finalCreationName = !string.IsNullOrEmpty(creationNameOverride) ? creationNameOverride : nodeName;
            
            // [Reverted] Remove Deep Identify Logic as per user request
            // We trust the input name directly (e.g. "Clockwork.Core.Sequence.Passthrough")
            MCPLogger.Info($"[CreateNode] Using direct name: {finalCreationName}");

            var nativeCmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, finalCreationName, x, y, false, false);
            _dynamoModel.ExecuteCommand(nativeCmd);
            
            if (n["value"] != null)
            {
                string propertyName = GetValuePropertyName(finalCreationName);
                if (!string.IsNullOrEmpty(propertyName))
                {
                    var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, propertyName, n["value"].ToString());
                    _dynamoModel.ExecuteCommand(updateCmd);
                }
            }

            HandlePreview(n, dynamoGuid);
        }

        // Helper for Python Code Update to reuse logic
        private void UpdatePythonCode(NodeModel node, string code)
        {
            bool injected = false;
            // Phase 1.1: Global Reflection
            try {
                var assemblies = AppDomain.CurrentDomain.GetAssemblies();
                Type cmdType = null;
                foreach (var asm in assemblies) {
                    cmdType = asm.GetType("Dynamo.Models.DynamoModel+UpdatePythonNodeCommand") ?? 
                              asm.GetType("Dynamo.Models.UpdatePythonNodeCommand");
                    if (cmdType != null) break;
                }

                if (cmdType != null) {
                    var constructor = cmdType.GetConstructors().FirstOrDefault(c => c.GetParameters().Length >= 2);
                    if (constructor != null) {
                        object[] p = constructor.GetParameters().Length == 3 
                            ? new object[] { node.GUID, code, "CPython3" }
                            : new object[] { node.GUID, code };
                        var pyCmd = constructor.Invoke(p) as DynamoModel.RecordableCommand;
                        _dynamoModel.ExecuteCommand(pyCmd);
                        injected = true;
                    }
                }
            } catch (Exception ex) {
                MCPLogger.Warning($"[Python] Command reflection failed: {ex.Message}");
            }

            // Phase 1.2: Dynamic Property
            if (!injected) {
                try {
                    var prop = node.GetType().GetProperty("Script") ?? node.GetType().GetProperty("Code");
                    if (prop != null) {
                        prop.SetValue(node, code);
                        var notifyMethod = node.GetType().GetMethod("OnNodeModified", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
                        if (notifyMethod != null) notifyMethod.Invoke(node, new object[] { true });
                    }
                } catch {}
            }
        }

        private void AdjustInputPorts(NodeModel node, int targetCount)
        {
             try {
                var addMethod = node.GetType().GetMethod("AddInput", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                var removeMethod = node.GetType().GetMethod("RemoveInput", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);

                if (addMethod != null) {
                    while (node.InPorts.Count < targetCount) addMethod.Invoke(node, null);
                }
                if (removeMethod != null) {
                    while (node.InPorts.Count > targetCount) removeMethod.Invoke(node, null);
                }
            } catch (Exception ex) {
                MCPLogger.Warning($"[Python] Failed to adjust ports: {ex.Message}");
            }
        }

        private void HandlePreview(JToken n, Guid guid)
        {
            if (n["preview"] != null)
            {
                bool isPreview = n["preview"].ToObject<bool>();
                if (!isPreview)
                {
                    var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, guid, "IsVisible", "false");
                    _dynamoModel.ExecuteCommand(updateCmd);
                }
            }
        }

        private string ResolveCreationName(string query)
        {
            if (string.IsNullOrEmpty(query)) return query;
            
            try 
            {
                // 1. 取得 SearchModel (嘗試多種路徑)
                object searchModel = null;
                try {
                    var modelType = _dynamoModel.GetType();
                    var searchModelProp = modelType.GetProperty("SearchModel", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                    searchModel = searchModelProp?.GetValue(_dynamoModel);
                } catch {}

                if (searchModel == null) {
                    try {
                        var vmProp = _vm.GetType().GetProperty("SearchViewModel", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        var svm = vmProp?.GetValue(_vm);
                        if (svm != null) {
                            var mProp = svm.GetType().GetProperty("Model", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                            searchModel = mProp?.GetValue(svm);
                        }
                    } catch {}
                }

                if (searchModel == null) return query;

                // 2. 取得搜尋條目集合 (Dynamic Scan)
                // 模仿 HandleToolsCall 的暴力掃描邏輯，尋找任何 IEnumerable<NodeSearchElement>
                IEnumerable<NodeSearchElement> elements = null;
                
                // Try Properties
                foreach (var p in searchModel.GetType().GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                {
                    if (typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(p.PropertyType))
                    {
                        try { elements = p.GetValue(searchModel) as IEnumerable<NodeSearchElement>; } catch {}
                        if (elements != null) break;
                    }
                }
                // Try Fields
                if (elements == null)
                {
                    foreach (var f in searchModel.GetType().GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                    {
                        if (typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(f.FieldType))
                        {
                            try { elements = f.GetValue(searchModel) as IEnumerable<NodeSearchElement>; } catch {}
                            if (elements != null) break;
                        }
                    }
                }

                if (elements == null) return query;

                // 3. 執行模糊比對
                var matches = new List<dynamic>();
                foreach (var entry in elements)
                {
                    string fn = entry.FullName ?? "";
                    string n = entry.Name ?? "";
                    
                    if (fn.Equals(query, StringComparison.OrdinalIgnoreCase)) return GetCreationName(entry);
                    if (n.Equals(query, StringComparison.OrdinalIgnoreCase)) matches.Add(new { Entry = entry, Weight = 10 });
                    else if (fn.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0) matches.Add(new { Entry = entry, Weight = 1 });
                }

                var bestMatch = matches.OrderByDescending(m => m.Weight).FirstOrDefault();
                if (bestMatch != null) 
                {
                    string resolved = GetCreationName(bestMatch.Entry);
                    if (!string.IsNullOrEmpty(resolved)) return resolved;
                }
            }
            catch (Exception ex) {
                MCPLogger.Warning($"[ResolveCreationName] Error: {ex.Message}");
            }
            
            return query;
        }

        private string GetCreationName(object entry)
        {
            var cnProp = entry.GetType().GetProperty("CreationName", BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            return cnProp?.GetValue(entry)?.ToString();
        }

        private string GetValuePropertyName(string fullName)
        {
            if (fullName.Contains("StringInput")) return "Value";
            if (fullName.Contains("IntegerSlider")) return "Value";
            if (fullName.Contains("DoubleSlider")) return "Value";
            if (fullName.Contains("Boolean")) return "Value";
            return null;
        }

        private void CreateConnection(JToken c)
        {
            string fromIdStr = c["from"]?.ToString();
            string toIdStr = c["to"]?.ToString();
            int fromIdx = c["fromPort"]?.ToObject<int>() ?? 0;
            int toIdx = c["toPort"]?.ToObject<int>() ?? 0;
            string toPortName = c["toPortName"]?.ToString();

            if (!_nodeIdMap.TryGetValue(fromIdStr, out Guid fromId)) fromId = Guid.Parse(fromIdStr);
            if (!_nodeIdMap.TryGetValue(toIdStr, out Guid toId)) toId = Guid.Parse(toIdStr);

            // --- [Optimization: Port Name Fallback] ---
            var toNode = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(n => n.GUID == toId);
            if (toNode != null && !string.IsNullOrEmpty(toPortName))
            {
                // 嘗試根據名稱尋找輸入埠位
                var port = toNode.InPorts.FirstOrDefault(p => 
                    p.Name.Equals(toPortName, StringComparison.OrdinalIgnoreCase));
                
                if (port != null)
                {
                    if (port.Index != toIdx)
                    {
                        MCPLogger.Info($"[Connection] Port mapping fallback: Name '{toPortName}' found at Index {port.Index} (Requested: {toIdx})");
                    }
                    toIdx = port.Index;
                }
                else
                {
                    MCPLogger.Warning($"[Connection] Port Name '{toPortName}' not found on node {toNode.Name}. Falling back to Index {toIdx}.");
                }
            }

            // 執行連線指令 (分別執行 Begin 與 End)
            try
            {
                _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(fromId, fromIdx, PortType.Output, DynamoModel.MakeConnectionCommand.Mode.Begin));
                _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(toId, toIdx, PortType.Input, DynamoModel.MakeConnectionCommand.Mode.End));
            }
            catch (Exception ex)
            {
                throw new Exception($"MakeConnectionCommand Failed ({fromIdStr} -> {toIdStr}): {ex.Message}");
            }
        }

        private void LoadCommonNodesCache()
        {
            try {
                string assemblyDir = System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
                string packageRoot = System.IO.Path.GetDirectoryName(assemblyDir);
                string jsonPath = System.IO.Path.Combine(packageRoot, "common_nodes.json");
                if (System.IO.File.Exists(jsonPath))
                    _commonNodesCache = JArray.Parse(System.IO.File.ReadAllText(jsonPath));
            } catch { } // Safe suppression for cache loading
        }
    }
}
