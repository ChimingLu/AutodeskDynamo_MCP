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
                        x = n.X,
                        y = n.Y
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
                        nodes = nodes
                    };

                    return JsonConvert.SerializeObject(statusData);
                } else if (action == "list_nodes") {
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

            MCPLogger.Info($"[CreateNode] 開始處理節點: {nodeName} (ID: {nodeIdStr})");

            Guid dynamoGuid = Guid.TryParse(nodeIdStr, out Guid parsedGuid) ? parsedGuid : Guid.NewGuid();
            if (!string.IsNullOrEmpty(nodeIdStr))
            {
                _nodeIdMap[nodeIdStr] = dynamoGuid;
            }

            // === 1. Code Block / Number ===
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

            // === 2. Strategy: Deep Identify & Creation ===
            string finalCreationName = !string.IsNullOrEmpty(creationNameOverride) ? creationNameOverride : nodeName;

            try {
                object searchModel = GetSearchModel();
                if (searchModel != null)
                {
                    var currentType = searchModel.GetType();
                    var elementsProp = currentType.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                                        .FirstOrDefault(p => typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(p.PropertyType));
                    
                    var elements = elementsProp?.GetValue(searchModel) as IEnumerable<NodeSearchElement>;
                    if (elements == null) {
                        var elementsField = currentType.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)
                                            .FirstOrDefault(f => typeof(IEnumerable<NodeSearchElement>).IsAssignableFrom(f.FieldType));
                        elements = elementsField?.GetValue(searchModel) as IEnumerable<NodeSearchElement>;
                    }

                    if (elements != null) {
                        var match = elements.FirstOrDefault(el => el.FullName == nodeName || el.Name == nodeName);
                        if (match != null) {
                            // --- DEEP IDENTITY SCAN ---
                            // We scan match and its potential 'Entry' for anything that looks like a GUID or real creation name
                            List<object> targets = new List<object> { match };
                            var entryProp = match.GetType().GetProperty("Entry", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                            var entry = entryProp?.GetValue(match);
                            if (entry != null) targets.Add(entry);

                            bool foundRealId = false;
                            foreach (var target in targets) {
                                var t = target.GetType();
                                // Scan Properties
                                foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                                    if (p.Name.Contains("Guid") || p.Name.Contains("ID") || p.Name == "CreationName") {
                                        var val = p.GetValue(target)?.ToString();
                                        if (!string.IsNullOrEmpty(val) && val != nodeName) {
                                            finalCreationName = val;
                                            foundRealId = true;
                                            break;
                                        }
                                    }
                                }
                                if (foundRealId) break;
                                // Scan Fields
                                foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance)) {
                                    if (f.Name.Contains("guid") || f.Name.Contains("id") || f.Name == "creationName") {
                                        var val = f.GetValue(target)?.ToString();
                                        if (!string.IsNullOrEmpty(val) && val != nodeName) {
                                            finalCreationName = val;
                                            foundRealId = true;
                                            break;
                                        }
                                    }
                                }
                                if (foundRealId) break;
                            }

                            if (foundRealId) {
                                MCPLogger.Info($"[CreateNode] Deep Scan Success: '{nodeName}' -> ID '{finalCreationName}'");
                            } else {
                                MCPLogger.Warning($"[CreateNode] Deep Scan found no unique ID for '{nodeName}', using default.");
                            }
                        }
                    }
                }
            } catch (Exception ex) {
                MCPLogger.Error($"[CreateNode] Resolution error: {ex.Message}");
            }

            MCPLogger.Info($"[CreateNode] Final creationName used: {finalCreationName}");
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

        private object GetSearchModel() {
            try {
                // In 3.0+, SearchModel is often in SearchViewModel via DynamoViewModel
                var svmProp = _vm.GetType().GetProperty("SearchViewModel", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                if (svmProp != null) {
                    var svmObj = svmProp.GetValue(_vm);
                    if (svmObj != null) {
                        var mProp = svmObj.GetType().GetProperty("Model", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
                        if (mProp != null) return mProp.GetValue(svmObj);
                    }
                }

                // Fallback to Scan
                foreach (var p in _dynamoModel.GetType().GetProperties(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)) {
                    if (p.PropertyType.Name.Contains("SearchModel")) return p.GetValue(_dynamoModel);
                }
                foreach (var f in _dynamoModel.GetType().GetFields(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance)) {
                    if (f.FieldType.Name.Contains("SearchModel")) return f.GetValue(_dynamoModel);
                }
            } catch {}
            return null;
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
            // Removed try-catch to allow bubbling
            string fromIdStr = c["from"]?.ToString();
            string toIdStr = c["to"]?.ToString();
            int fromIdx = c["fromPort"]?.ToObject<int>() ?? 0;
            int toIdx = c["toPort"]?.ToObject<int>() ?? 0;

            if (!_nodeIdMap.TryGetValue(fromIdStr, out Guid fromId)) fromId = Guid.Parse(fromIdStr);
            if (!_nodeIdMap.TryGetValue(toIdStr, out Guid toId)) toId = Guid.Parse(toIdStr);
            
            _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(fromId, fromIdx, PortType.Output, DynamoModel.MakeConnectionCommand.Mode.Begin));
            _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(toId, toIdx, PortType.Input, DynamoModel.MakeConnectionCommand.Mode.End));
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
