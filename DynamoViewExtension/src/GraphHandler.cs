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
using Dynamo.Graph.Annotations;
using Dynamo.Graph.Workspaces;

namespace DynamoMCPListener
{
    [Autodesk.DesignScript.Runtime.IsVisibleInDynamoLibrary(false)]
    public class GraphHandler
    {
        private const string BuildMarker = "GraphHandler-2026-05-29-status-guard-v2";
        private DynamoViewModel _vm;
        private DynamoModel _dynamoModel;
        private JArray _commonNodesCache;
        private string _sessionId;
        private Dictionary<string, Guid> _nodeIdMap; // 字串 ID -> Dynamo GUID ?��?�?

        public GraphHandler(DynamoViewModel vm, string sessionId)
        {
            _vm = vm;
            _dynamoModel = vm.Model;
            _sessionId = sessionId;
            _nodeIdMap = new Dictionary<string, Guid>();
            MCPLogger.Info($"[GraphHandler] Initialized marker={BuildMarker} session={_sessionId}");
        }

        public string HandleCommand(string jsonLine)
        {
            try
            {
                var data = JObject.Parse(jsonLine);
                var errors = new List<string>();

                // 0. Handle Actions (like clear_graph)
                string action = data["action"]?.ToString();
                if (string.IsNullOrWhiteSpace(action))
                {
                    MCPLogger.Info($"[GraphHandler] Non-action payload marker={BuildMarker}: {jsonLine}");
                    if (data["status"] != null || data["sessionId"] != null)
                    {
                        return "{\"status\": \"ok\", \"message\": \"status acknowledged\"}";
                    }

                    // Backward compatibility: execute_dynamo_instructions sends payload with
                    // nodes/connectors but without an explicit action field.
                    if (data["nodes"] != null || data["connectors"] != null)
                    {
                        action = "legacy_execute";
                    }
                    else
                    {
                        return "{\"status\": \"ignored\", \"message\": \"Missing action\"}";
                    }
                }

                if (action == "clear_graph")
                {
                    // This must be run on UI thread, handled by WebSocketClient dispatcher
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        _nodeIdMap.Clear();
                        return "{\"status\": \"ok\", \"message\": \"Workspace already empty\"}";
                    }

                    var nodesToDelete = workspace.Nodes.Select(n => n.GUID).ToList();
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
                    MCPLogger.Info($"[GraphHandler] get_graph_status marker={BuildMarker}");
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        var emptyStatusData = new
                        {
                            sessionId = _sessionId,
                            processId = System.Diagnostics.Process.GetCurrentProcess().Id,
                            workspace = new
                            {
                                name = "Home",
                                fileName = ""
                            },
                            workspaceName = "Home",
                            nodeCount = 0,
                            connectorCount = 0,
                            nodes = new object[0],
                            connectors = new object[0],
                            warning = "目前尚未開啟可分析的 Dynamo 工作區。"
                        };

                        return JsonConvert.SerializeObject(emptyStatusData);
                    }

                    var nodes = workspace.Nodes.Select(n => new
                    {
                        id = n.GUID.ToString(),
                        name = n.Name,
                        fullName = n.GetType().FullName,
                        creationName = n.GetType().GetProperty("CreationName")?.GetValue(n)?.ToString() ?? n.Name,
                        x = n.X,
                        y = n.Y,
                        isInput = GetBoolProperty(n, "IsSetAsInput"),
                        isOutput = GetBoolProperty(n, "IsSetAsOutput")
                    }).ToList();

                    var connectors = workspace.Connectors
                        .Where(c => c?.Start?.Owner != null && c?.End?.Owner != null)
                        .Select(c => new
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
                            name = workspace.Name,
                            fileName = workspace.FileName
                        },
                        workspaceName = workspace.Name,
                        nodeCount = nodes.Count,
                        connectorCount = connectors.Count,
                        nodes = nodes,
                        connectors = connectors
                    };

                    return JsonConvert.SerializeObject(statusData);
                }

                if (action == "debug_group_api")
                {
                    return DebugGroupApi();
                }

                if (action == "create_group")
                {
                    return CreateGroup(data);
                }
                
                // === MCP Resources Layer: Structured Data Queries ===
                if (action == "get_nodes_structured")
                {
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        return WorkspaceUnavailableError(action);
                    }

                    var nodes = workspace.Nodes.Select(n => {
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
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        return WorkspaceUnavailableError(action);
                    }

                    var connectors = workspace.Connectors
                        .Where(c => c?.Start?.Owner != null && c?.End?.Owner != null)
                        .Select(c => new
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
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        return WorkspaceUnavailableError(action);
                    }

                    var selected = workspace.Nodes
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
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        return WorkspaceUnavailableError(action);
                    }

                    var errorNodes = workspace.Nodes
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
                    var workspace = GetWorkspace();
                    if (workspace == null)
                    {
                        return WorkspaceUnavailableError(action);
                    }

                    string targetId = data["nodeId"]?.ToString();
                    if (string.IsNullOrEmpty(targetId))
                    {
                        return "{\"status\": \"error\", \"message\": \"Missing nodeId parameter\"}";
                    }

                    Guid targetGuid;
                    if (!Guid.TryParse(targetId, out targetGuid))
                    {
                        // ?�試�?ID ?��?表查??
                        if (!_nodeIdMap.TryGetValue(targetId, out targetGuid))
                        {
                            return "{\"status\": \"error\", \"message\": \"Node not found\"}";
                        }
                    }

                    var node = workspace.Nodes.FirstOrDefault(n => n.GUID == targetGuid);
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
                            connectedFrom = p.IsConnected ? workspace.Connectors
                                .Where(c => c.End.Owner.GUID == node.GUID && c.End.Index == p.Index)
                                .Select(c => c.Start.Owner.GUID.ToString())
                                .FirstOrDefault() : null
                        }).ToList(),
                        outputs = node.OutPorts.Select(p => new
                        {
                            name = p.Name,
                            type = p.PortType.ToString(),
                            connectedTo = workspace.Connectors
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
                    var displayLines = new List<string> { $"?? ?��? '{filter}' ?�到 {results.Count} ?��???(?��??��? 50 ??:\n" };
                    foreach (var n in results) {
                        displayLines.Add($"- **{n.name}**");
                        displayLines.Add($"  fullName: `{n.fullName}`");
                        displayLines.Add($"  creationName: `{n.creationName}`");
                        if (!string.IsNullOrEmpty(n.description)) displayLines.Add($"  說�?: {n.description}");
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
                MCPLogger.Error("Error executing instructions", ex);
                return JsonConvert.SerializeObject(new { status = "error", message = ex.Message });
            }
        }

        private WorkspaceModel GetWorkspace()
        {
            return _dynamoModel?.CurrentWorkspace;
        }

        private string WorkspaceUnavailableError(string action)
        {
            return JsonConvert.SerializeObject(new
            {
                status = "error",
                action,
                message = "目前尚未開啟可分析的 Dynamo 工作區。"
            });
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

            // Variadic nodes (List.Create, String.Concat, ...) support inputCount as well
            if (n["inputCount"] != null)
            {
                var createdNode = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(nd => nd.GUID == dynamoGuid);
                if (createdNode != null) AdjustInputPorts(createdNode, n["inputCount"].ToObject<int>());
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

            HandleIOFlags(n, guid);
        }

        // Sets NodeModel.IsSetAsInput / IsSetAsOutput (Dynamo Player / Generative Design "Is Input" / "Is Output")
        private void HandleIOFlags(JToken n, Guid guid)
        {
            JToken inputFlag = n["isInput"] ?? n["IsSetAsInput"];
            JToken outputFlag = n["isOutput"] ?? n["IsSetAsOutput"];
            if (inputFlag == null && outputFlag == null) return;

            var node = _dynamoModel.CurrentWorkspace.Nodes.FirstOrDefault(nd => nd.GUID == guid);
            if (node == null) return;

            TrySetBoolProperty(node, "IsSetAsInput", inputFlag);
            TrySetBoolProperty(node, "IsSetAsOutput", outputFlag);
        }

        private static bool? GetBoolProperty(NodeModel node, string propertyName)
        {
            try
            {
                return node.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public)?.GetValue(node) as bool?;
            }
            catch
            {
                return null;
            }
        }

        private void TrySetBoolProperty(NodeModel node, string propertyName, JToken flag)
        {
            if (flag == null) return;
            try
            {
                var prop = node.GetType().GetProperty(propertyName, BindingFlags.Instance | BindingFlags.Public);
                if (prop != null && prop.CanWrite)
                {
                    prop.SetValue(node, flag.ToObject<bool>());
                }
                else
                {
                    MCPLogger.Warning($"[IOFlags] {propertyName} not writable on {node.GetType().Name}");
                }
            }
            catch (Exception ex)
            {
                MCPLogger.Warning($"[IOFlags] Failed to set {propertyName}: {ex.Message}");
            }
        }

        private string ResolveCreationName(string query)
        {
            if (string.IsNullOrEmpty(query)) return query;
            
            try 
            {
                // 1. ?��? SearchModel (?�試多種路�?)
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

                // 2. ?��??��?條目?��? (Dynamic Scan)
                // 模仿 HandleToolsCall ?�暴?��??��?輯�?尋找任�? IEnumerable<NodeSearchElement>
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

                // 3. ?��?模�?比�?
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
                // ?�試?��??�稱尋找輸入?��?
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

            // ?��?????�令 (?�別?��? Begin ??End)
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
                {
                    using (System.IO.StreamReader r = new System.IO.StreamReader(jsonPath))
                    {
                        string json = r.ReadToEnd();
                        _commonNodesCache = JArray.Parse(json);
                    }
                }
            } catch { _commonNodesCache = new JArray(); }
        }

        private string DebugGroupApi()
        {
            var sb = new System.Text.StringBuilder();
            var assemblies = System.AppDomain.CurrentDomain.GetAssemblies();
            
            foreach (var asm in assemblies)
            {
                try
                {
                    var types = asm.GetTypes();
                    foreach (var t in types)
                    {
                        if (t.Name == "AnnotationModel" || t.Name == "CreateAnnotationCommand" || t.Name == "AddModelToGroupCommand")
                        {
                            sb.AppendLine($"[{asm.GetName().Name}] {t.FullName}");
                            foreach (var ctor in t.GetConstructors(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance))
                            {
                                var pStr = string.Join(", ", ctor.GetParameters().Select(p => $"{p.ParameterType.Name} {p.Name}"));
                                sb.AppendLine($"  .ctor({pStr})");
                            }
                        }
                    }
                }
                catch { }
            }

            // Also report workspace annotations count
            sb.AppendLine($"\nCurrent Annotations: {_dynamoModel.CurrentWorkspace.Annotations.Count()}");
            
            var result = sb.ToString();
            MCPLogger.Info(result);
            return JsonConvert.SerializeObject(new { status = "ok", debug = result });
        }

        private DynamoModel.RecordableCommand CreateAnnotationCommandCompat(
            Guid annotationGuid,
            string title,
            string description,
            double x,
            double y)
        {
            // Every known Dynamo version (2.3 ~ 4.x) builds the group from the nodes that are
            // currently selected; the IEnumerable<Guid> constructors do NOT seed members, they only
            // use the first GUID as the annotation id. So always pass our own fresh annotation GUID.
            var commandType = typeof(DynamoModel.CreateAnnotationCommand);
            var annotationText = string.IsNullOrWhiteSpace(description)
                ? title
                : $"{title}{Environment.NewLine}{description}";

            var ctors = commandType.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var guidList = new List<Guid> { annotationGuid };

            object BuildIdArg(Type paramType)
            {
                if (paramType == typeof(Guid))
                    return annotationGuid;
                if (paramType.IsAssignableFrom(typeof(List<Guid>)))
                    return guidList;
                return null;
            }

            // Prefer Guid-first constructors, then IEnumerable<Guid>; prefer (title, description) when available.
            var ordered = ctors
                .Where(c => c.GetParameters().Length == 5 || c.GetParameters().Length == 6)
                .OrderBy(c => c.GetParameters()[0].ParameterType == typeof(Guid) ? 0 : 1)
                .ThenByDescending(c => c.GetParameters().Length);

            foreach (var ctor in ordered)
            {
                var parameters = ctor.GetParameters();
                var idArg = BuildIdArg(parameters[0].ParameterType);
                if (idArg == null)
                    continue;

                try
                {
                    if (parameters.Length == 6)
                        return (DynamoModel.RecordableCommand)ctor.Invoke(new object[] { idArg, title, description, x, y, false });

                    return (DynamoModel.RecordableCommand)ctor.Invoke(new object[] { idArg, annotationText, x, y, false });
                }
                catch (Exception ex)
                {
                    MCPLogger.Warning($"[CreateGroup] CreateAnnotationCommand ctor invoke failed ({ctor}): {ex.Message}");
                }
            }

            throw new MissingMethodException("Unsupported CreateAnnotationCommand constructor.");
        }

        private HashSet<Guid> GetAnnotationNodeIds(AnnotationModel annotation)
        {
            var ids = new HashSet<Guid>();
            if (annotation == null)
                return ids;

            try
            {
                var nodesProp = annotation.GetType().GetProperty("Nodes", BindingFlags.Public | BindingFlags.Instance);
                if (nodesProp?.GetValue(annotation) is System.Collections.IEnumerable members)
                {
                    foreach (var member in members)
                    {
                        if (member is NodeModel nodeMember)
                        {
                            ids.Add(nodeMember.GUID);
                            continue;
                        }

                        var guidProp = member?.GetType().GetProperty("GUID", BindingFlags.Public | BindingFlags.Instance);
                        var guidObj = guidProp?.GetValue(member);
                        if (guidObj is Guid g)
                        {
                            ids.Add(g);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                MCPLogger.Warning($"[CreateGroup] Failed to inspect annotation members: {ex.Message}");
            }

            return ids;
        }

        private HashSet<Guid> GetGroupedNodeIds(WorkspaceModel workspace)
        {
            var grouped = new HashSet<Guid>();
            if (workspace?.Annotations == null)
                return grouped;

            foreach (var annotation in workspace.Annotations)
            {
                foreach (var id in GetAnnotationNodeIds(annotation))
                {
                    grouped.Add(id);
                }
            }

            return grouped;
        }

        private DynamoModel.RecordableCommand CreateSelectModelCommandCompat(Guid modelGuid)
        {
            return CreateSelectModelCommandCompat(new[] { modelGuid });
        }

        // SelectModelCommand semantics (Dynamo 2.x+): Guid.Empty clears the selection; a multi-GUID
        // command adds every listed model that is not yet selected.
        private DynamoModel.RecordableCommand CreateSelectModelCommandCompat(IEnumerable<Guid> modelGuids)
        {
            var commandType = typeof(DynamoModel.SelectModelCommand);
            var ctors = commandType.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            var guids = modelGuids?.ToArray() ?? new Guid[0];
            var modelGuid = guids.FirstOrDefault();

            object BuildFirstArg(Type firstType)
            {
                if (guids.Length == 1 && firstType == typeof(Guid))
                    return modelGuid;

                if (guids.Length == 1 && firstType == typeof(string))
                    return modelGuid.ToString();

                if (firstType != typeof(string) && typeof(System.Collections.IEnumerable).IsAssignableFrom(firstType))
                {
                    if (!firstType.IsGenericType)
                    {
                        return guids;
                    }

                    var genericArg = firstType.GetGenericArguments().FirstOrDefault();
                    if (genericArg == typeof(Guid) || genericArg == typeof(object))
                        return guids.ToList();

                    if (genericArg == typeof(string))
                        return guids.Select(g => g.ToString()).ToList();
                }

                return null;
            }

            object BuildSecondArg(Type secondType)
            {
                if (secondType == typeof(int))
                    return 0;

                if (secondType.IsEnum)
                    return Enum.ToObject(secondType, 0);

                if (secondType.IsValueType)
                    return Activator.CreateInstance(secondType);

                return null;
            }

            foreach (var ctor in ctors)
            {
                var parameters = ctor.GetParameters();

                try
                {
                    if (parameters.Length == 1)
                    {
                        var arg0 = BuildFirstArg(parameters[0].ParameterType);
                        if (arg0 != null)
                            return (DynamoModel.RecordableCommand)ctor.Invoke(new[] { arg0 });
                    }

                    if (parameters.Length == 2)
                    {
                        var arg0 = BuildFirstArg(parameters[0].ParameterType);
                        var arg1 = BuildSecondArg(parameters[1].ParameterType);
                        if (arg0 != null && arg1 != null)
                            return (DynamoModel.RecordableCommand)ctor.Invoke(new[] { arg0, arg1 });
                    }
                }
                catch (Exception ex)
                {
                    MCPLogger.Warning($"[CreateGroup] SelectModelCommand ctor invoke failed ({ctor}): {ex.Message}");
                }
            }

            var ctorSignatures = string.Join(", ",
                ctors.Select(c =>
                {
                    var p = c.GetParameters();
                    return $"({string.Join(", ", p.Select(x => x.ParameterType.Name))})";
                }));

            MCPLogger.Warning($"[CreateGroup] SelectModelCommand constructors discovered: {ctorSignatures}");

            throw new MissingMethodException("Unsupported SelectModelCommand constructor.");
        }

        private AnnotationModel WaitForAnnotation(WorkspaceModel workspace, Guid annotationGuid, int timeoutMs = 2000, ISet<Guid> annotationGuidsBefore = null)
        {
            if (workspace?.Annotations == null)
                return null;

            // Match the requested GUID first; otherwise (when a pre-command snapshot is given)
            // accept the single annotation that did not exist before. Never fall back to node GUIDs.
            AnnotationModel Find()
            {
                var exact = workspace.Annotations.FirstOrDefault(a => a?.GUID == annotationGuid);
                if (exact != null || annotationGuidsBefore == null)
                    return exact;
                return workspace.Annotations.FirstOrDefault(a => a != null && !annotationGuidsBefore.Contains(a.GUID));
            }

            var deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
            while (DateTime.UtcNow < deadline)
            {
                var found = Find();
                if (found != null)
                    return found;

                System.Threading.Thread.Sleep(50);
            }

            return Find();
        }

        private void ClearSelectionCompat(WorkspaceModel workspace)
        {
            try
            {
                // SelectModelCommand with Guid.Empty clears DynamoSelection (which is internal to DynamoCore).
                _dynamoModel.ExecuteCommand(CreateSelectModelCommandCompat(Guid.Empty));
            }
            catch (Exception ex)
            {
                MCPLogger.Warning($"[CreateGroup] Clear selection command failed: {ex.Message}");
            }

            if (workspace == null)
                return;

            // Older runtimes (Dynamo 2.6) read ModelBase.IsSelected directly, so make sure nothing stays flagged.
            try
            {
                foreach (var n in workspace.Nodes)
                    if (n.IsSelected) n.IsSelected = false;
                foreach (var note in workspace.Notes)
                    if (note.IsSelected) note.IsSelected = false;
                foreach (var a in workspace.Annotations)
                    if (a.IsSelected) a.IsSelected = false;
            }
            catch (Exception ex)
            {
                MCPLogger.Warning($"[CreateGroup] Failed to reset IsSelected flags: {ex.Message}");
            }
        }

        private int SelectModelsCompat(IEnumerable<Dynamo.Graph.ModelBase> models)
        {
            var targets = (models ?? Enumerable.Empty<Dynamo.Graph.ModelBase>()).Where(m => m != null).ToList();
            var toSelect = targets.Where(m => !m.IsSelected).Select(m => m.GUID).ToList();

            if (toSelect.Any())
            {
                try
                {
                    // Goes through DynamoSelection, which keeps ModelBase.IsSelected in sync.
                    _dynamoModel.ExecuteCommand(CreateSelectModelCommandCompat(toSelect));
                }
                catch (Exception ex)
                {
                    MCPLogger.Warning($"[CreateGroup] SelectModelCommand failed for {toSelect.Count} model(s): {ex.Message}");
                }
            }

            // Fallback: Dynamo 2.x builds groups from ModelBase.IsSelected, so set the flag directly if needed.
            foreach (var model in targets.Where(m => !m.IsSelected))
            {
                try
                {
                    model.IsSelected = true;
                }
                catch (Exception ex)
                {
                    MCPLogger.Warning($"[CreateGroup] Direct selection failed for {model.GUID}: {ex.Message}");
                }
            }

            return targets.Count(m => m.IsSelected);
        }

        private bool TrySelectAnnotationCompat(WorkspaceModel workspace, Guid annotationGuid)
        {
            var annotation = WaitForAnnotation(workspace, annotationGuid, 500);
            if (annotation == null)
            {
                MCPLogger.Warning($"[CreateGroup] Annotation {annotationGuid} not found in workspace.");
                return false;
            }

            // AddModelToGroupCommand targets the first selected annotation, so only this one may be selected.
            ClearSelectionCompat(workspace);
            if (SelectModelsCompat(new[] { annotation }) == 1)
                return true;

            MCPLogger.Warning($"[CreateGroup] Annotation {annotationGuid} could not be selected.");
            return false;
        }

        private void AddNodesToGroupWithFallback(WorkspaceModel workspace, AnnotationModel annotation, IEnumerable<Guid> nodeGuids)
        {
            var ids = nodeGuids?.Distinct().ToList() ?? new List<Guid>();
            if (!ids.Any() || annotation == null)
                return;

            if (!TrySelectAnnotationCompat(workspace, annotation.GUID))
            {
                MCPLogger.Warning($"[CreateGroup] Unable to select annotation {annotation.GUID} before grouping.");
                return;
            }

            try
            {
                _dynamoModel.ExecuteCommand(new DynamoModel.AddModelToGroupCommand(ids));
            }
            catch (Exception bulkEx)
            {
                MCPLogger.Warning($"[CreateGroup] Bulk add failed: {bulkEx.Message}");
            }

            var members = GetAnnotationNodeIds(annotation);
            var stillMissing = ids.Where(id => !members.Contains(id)).ToList();
            if (!stillMissing.Any())
                return;

            MCPLogger.Warning($"[CreateGroup] {stillMissing.Count} node(s) still missing after bulk add, fallback to single add.");
            foreach (var id in stillMissing)
            {
                try
                {
                    if (!TrySelectAnnotationCompat(workspace, annotation.GUID))
                    {
                        MCPLogger.Warning($"[CreateGroup] Skip node {id}, target annotation is not selectable.");
                        continue;
                    }
                    _dynamoModel.ExecuteCommand(new DynamoModel.AddModelToGroupCommand(new[] { id }));
                }
                catch (Exception ex)
                {
                    MCPLogger.Warning($"[CreateGroup] Failed to add node {id}: {ex.Message}");
                }
            }
        }

        private string CreateGroup(JToken data)
        {
            var nodeIds = data["nodeIds"]?.ToObject<List<string>>() ?? new List<string>();
            string title = data["title"]?.ToString() ?? "New Group";
            string description = data["description"]?.ToString() ?? "";
            string color = data["color"]?.ToString() ?? "#FFC1D5E0";
            var workspace = GetWorkspace();

            if (workspace == null)
            {
                return JsonConvert.SerializeObject(new { status = "error", message = "Workspace unavailable" });
            }

            // Resolve node IDs
            var nodesToGroup = new List<NodeModel>();
            var groupedNodeIds = GetGroupedNodeIds(workspace);
            int skippedAlreadyGrouped = 0;
            foreach (var idStr in nodeIds)
            {
                Guid guid;
                if (Guid.TryParse(idStr, out Guid parsed)) guid = parsed;
                else if (_nodeIdMap.TryGetValue(idStr, out Guid mapped)) guid = mapped;
                else continue;

                var node = workspace.Nodes.FirstOrDefault(n => n.GUID == guid);
                if (node == null) continue;

                if (groupedNodeIds.Contains(node.GUID))
                {
                    skippedAlreadyGrouped++;
                    continue;
                }

                if (!nodesToGroup.Contains(node))
                    nodesToGroup.Add(node);
            }

            if (!nodesToGroup.Any())
            {
                MCPLogger.Warning("[CreateGroup] No eligible nodes found (all missing or already grouped).");
                return JsonConvert.SerializeObject(new
                {
                    status = "skipped",
                    message = "No eligible nodes found",
                    skippedAlreadyGrouped
                });
            }

            // Calculate bounding box for group position
            double minX = nodesToGroup.Min(n => n.X);
            double minY = nodesToGroup.Min(n => n.Y);
            Guid annotationGuid = Guid.NewGuid();
            var nodeGuids = nodesToGroup.Select(n => n.GUID).ToList();

            int addedCount;
            Guid effectiveAnnotationGuid;
            try
            {
                // Step 1: Dynamo builds the group from the current selection, so select exactly the target
                // nodes. With an empty selection, Dynamo 2.x silently refuses to create a group as soon as
                // any other group exists (CheckIfModelExistsInSameGroup), which broke every group after the first.
                ClearSelectionCompat(workspace);
                int selectedCount = SelectModelsCompat(nodesToGroup);
                if (selectedCount < nodesToGroup.Count)
                {
                    MCPLogger.Warning($"[CreateGroup] Only {selectedCount}/{nodesToGroup.Count} nodes could be selected before grouping.");
                }

                // Step 2: Create the annotation (group container) and identify it by GUID or by diffing the collection.
                var annotationGuidsBefore = new HashSet<Guid>(workspace.Annotations.Select(a => a.GUID));
                _dynamoModel.ExecuteCommand(CreateAnnotationCommandCompat(
                    annotationGuid, title, description, minX - 10, minY - 55));

                var createdAnnotation = WaitForAnnotation(workspace, annotationGuid, 1000, annotationGuidsBefore);
                if (createdAnnotation == null)
                {
                    throw new InvalidOperationException(
                        $"Create group failed: Dynamo did not create an annotation (selected {selectedCount}/{nodesToGroup.Count} nodes).");
                }
                effectiveAnnotationGuid = createdAnnotation.GUID;

                // Step 3: Add any nodes the runtime did not pick up from the selection.
                var members = GetAnnotationNodeIds(createdAnnotation);
                var missing = nodeGuids.Where(g => !members.Contains(g)).ToList();
                if (missing.Any())
                {
                    MCPLogger.Warning($"[CreateGroup] Annotation {effectiveAnnotationGuid} missing {missing.Count} node(s) after creation, adding explicitly.");
                    AddNodesToGroupWithFallback(workspace, createdAnnotation, missing);
                    members = GetAnnotationNodeIds(createdAnnotation);
                }

                addedCount = nodeGuids.Count(g => members.Contains(g));
                if (addedCount == 0)
                {
                    throw new InvalidOperationException("Create group failed: no nodes were added to annotation.");
                }

                // Step 4: Set background color
                if (!string.IsNullOrEmpty(color))
                {
                    try
                    {
                        _dynamoModel.ExecuteCommand(new DynamoModel.UpdateModelValueCommand(
                            workspace.Guid, effectiveAnnotationGuid, "Background", color));
                    }
                    catch (Exception ex)
                    {
                        MCPLogger.Warning($"[CreateGroup] Failed to set color: {ex.Message}");
                    }
                }
            }
            finally
            {
                // Leave nothing selected so the next group neither nests nor picks up stale members.
                ClearSelectionCompat(workspace);
            }

            MCPLogger.Info($"[CreateGroup] Created group '{title}' with {addedCount}/{nodesToGroup.Count} nodes at ({minX:F0}, {minY:F0}), annotation={effectiveAnnotationGuid}. Skipped already grouped={skippedAlreadyGrouped}.");

            return JsonConvert.SerializeObject(new
            {
                status = "ok",
                message = "Group created",
                requested = nodeIds.Count,
                eligible = nodesToGroup.Count,
                added = addedCount,
                annotationId = effectiveAnnotationGuid.ToString(),
                skippedAlreadyGrouped
            });
        }
    }
}
