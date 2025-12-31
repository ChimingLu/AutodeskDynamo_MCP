using System;
using System.Collections.Generic;
using System.Linq;
using Dynamo.Graph.Nodes;
using Dynamo.Models;
using Dynamo.ViewModels;
using Dynamo.Wpf.Extensions;
using Newtonsoft.Json.Linq;
using Autodesk.DesignScript.Runtime;
using Dynamo.Search.SearchElements;
using Dynamo.Graph.Nodes.CustomNodes;

namespace DynamoMCPListener
{
    [IsVisibleInDynamoLibrary(false)]
    public class GraphHandler
    {
        private DynamoViewModel _vm;
        
        // Map user-provided IDs (e.g., "node1") to actual Dynamo GUIDs
        private Dictionary<string, Guid> _nodeIdMap = new Dictionary<string, Guid>();

        // 全域節點索引，加速搜尋與放置
        private static Dictionary<string, NodeSearchElement> _globalNodeIndex = null;
        private static readonly object _indexLock = new object();

        public GraphHandler(ViewLoadedParams p)
        {
            if (p.DynamoWindow.DataContext is DynamoViewModel vm)
            {
                _vm = vm;
            }
        }

        public GraphHandler(DynamoViewModel vm)
        {
            _vm = vm;
        }

        public string HandleCommand(string json)
        {
            if (_vm == null) 
            {
                MCPLogger.Error("ViewModel is null");
                return CreateErrorResponse("ViewModel is null");
            }
            
            try 
            {
                JObject root = JObject.Parse(json);
                string action = root["action"]?.ToString();

                if (action == "list_nodes")
                {
                    string detail = root["detail"]?.ToString() ?? "basic";
                    return ListNodes(root["filter"]?.ToString(), root["scope"]?.ToString(), detail);
                }

                if (action == "get_graph_status")
                {
                    return GetGraphStatus();
                }

                if (action == "reload_config")
                {
                    _commonNodesCache = null;
                    LoadCommonNodesCache();
                    _searchCache.Clear();
                    return "{\"status\": \"Config reloaded\"}";
                }
                
                // 1. Create Nodes
                var nodes = root["nodes"] as JArray;
                if (nodes != null)
                {
                    foreach (var n in nodes)
                    {
                        CreateNode(n);
                    }
                }

                // 2. Create Connections
                var conns = root["connectors"] as JArray;
                if (conns != null)
                {
                    foreach (var c in conns)
                    {
                        CreateConnection(c);
                    }
                }

                return "{\"status\": \"ok\"}";
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"HandleCommand failed: {ex.Message}", ex);
                return CreateErrorResponse(ex.Message, ex.StackTrace);
            }
        }

        private string GetGraphStatus()
        {
            var result = new JObject();
            var nodeList = new JArray();

            try
            {
                var workspace = _vm.Model.CurrentWorkspace;
                foreach (var node in workspace.Nodes)
                {
                    var nodeObj = new JObject();
                    nodeObj["id"] = node.GUID.ToString();
                    nodeObj["name"] = node.Name;
                    nodeObj["state"] = node.State.ToString();
                    
                    // Get warning/error messages if any
                    // Note: Dynamo nodes have a 'ToolTipText' or validation properties
                    // In recent Dynamo versions, node.ErrorHighlight is used or specific properties.
                    // A simple way is to check the node's state and potentially its warnings.
                    
                    var messages = new JArray();
                    // Some common ways to get errors in Dynamo API:
                    // node.ToolTipText often contains the error message shown in the UI
                    // Or node.ValidationData (if available in this version)
                    
                    // We'll collect the Name and State for now, as getting the exact string 
                    // can vary by Dynamo version/internal implementation.
                    
                    nodeList.Add(nodeObj);
                }

                result["nodes"] = nodeList;
                result["status"] = "ok";
            }
            catch (Exception ex)
            {
                return CreateErrorResponse("Failed to get graph status: " + ex.Message);
            }

            return result.ToString();
        }

        private string CreateErrorResponse(string message, string details = null)
        {
            var error = new JObject();
            error["error"] = message;
            if (!string.IsNullOrEmpty(details))
            {
                error["details"] = details;
            }
            return error.ToString();
        }

        private static List<JObject> _commonNodesCache = null;
        private static Dictionary<string, string> _searchCache = new Dictionary<string, string>();
        private static DateTime _cacheTime = DateTime.MinValue;

        private void BuildGlobalIndex()
        {
            if (_globalNodeIndex != null) return;

            lock (_indexLock)
            {
                if (_globalNodeIndex != null) return;

                MCPLogger.Info("Building global node index...");
                var index = new Dictionary<string, NodeSearchElement>(StringComparer.OrdinalIgnoreCase);
                
                try
                {
                    var searchModel = _vm.Model.SearchModel;
                    foreach (var entry in searchModel.Entries)
                    {
                        // 優先使用 FullName 作為 key
                        if (!string.IsNullOrEmpty(entry.FullName) && !index.ContainsKey(entry.FullName))
                        {
                            index[entry.FullName] = entry;
                        }

                        // 同時保留 CreationName 的對照，以便於簡稱搜尋
                        if (!string.IsNullOrEmpty(entry.CreationName) && !index.ContainsKey(entry.CreationName))
                        {
                            index[entry.CreationName] = entry;
                        }
                    }
                    _globalNodeIndex = index;
                    MCPLogger.Info($"Index built with {_globalNodeIndex.Count} entries.");
                }
                catch (Exception ex)
                {
                    MCPLogger.Error($"Failed to build global index: {ex.Message}");
                }
            }
        }

        private string ListNodes(string filter, string scope, string detail = "basic")
        {
            var result = new JObject();
            var nodeList = new JArray();

            // 1. Load Common Nodes (with caching)
            if (_commonNodesCache == null)
            {
                LoadCommonNodesCache();
            }

            // Normalization
            filter = filter?.Trim().ToLowerInvariant() ?? "";
            bool isSearchAll = (scope == "all");
            int maxResults = isSearchAll ? MCPConfig.ALL_SCOPE_MAX_RESULTS : MCPConfig.DEFAULT_MAX_RESULTS;

            // Check cache (valid for 5 minutes)
            string cacheKey = $"{filter}|{scope}|{detail}";
            if ((DateTime.Now - _cacheTime).TotalMinutes < MCPConfig.CACHE_EXPIRY_MINUTES 
                && _searchCache.ContainsKey(cacheKey))
            {
                MCPLogger.Debug($"Cache hit for: {cacheKey}");
                return _searchCache[cacheKey];
            }

            // 2. Search Logic
            // Step 2a: Find matches in Common Nodes (Priority)
            var commonMatches = new List<JObject>();
            if (_commonNodesCache != null)
            {
                foreach (var node in _commonNodesCache)
                {
                    string name = node["name"]?.ToString().ToLowerInvariant() ?? "";
                    string desc = node["description"]?.ToString().ToLowerInvariant() ?? "";
                    
                    if (string.IsNullOrEmpty(filter) || name.Contains(filter) || desc.Contains(filter))
                    {
                        var nodeObj = CreateNodeObject(node, detail, true);
                        commonMatches.Add(nodeObj);
                    }
                }
            }

            // Step 2b: Search Global Nodes
            var globalMatches = new List<JObject>();
            var searchModel = _vm.Model.SearchModel;
            var entries = searchModel.Entries;
            
            foreach (var entry in entries)
            {
                if (commonMatches.Count + globalMatches.Count >= maxResults) break;

                // Check duplication with common nodes (by FullName)
                string fullName = entry.FullName;
                bool alreadyAdded = commonMatches.Any(n => n["fullName"]?.ToString() == fullName);
                if (alreadyAdded) continue;

                string name = entry.CreationName.ToLowerInvariant();
                string entryFullName = entry.FullName.ToLowerInvariant();
                
                // Strict Filter for Default Scope
                if (!string.IsNullOrEmpty(filter))
                {
                    if (!name.Contains(filter) && !entryFullName.Contains(filter)) continue;
                }
                else
                {
                    // If no filter and default scope, don't spam global nodes.
                    if (!isSearchAll) continue;
                }

                // Add Global Node
                var nodeObj = new JObject();
                nodeObj["name"] = entry.CreationName;
                nodeObj["fullName"] = entry.FullName;
                nodeObj["isCommon"] = false;
                
                // Detail level control
                if (detail == "standard" || detail == "full")
                {
                    nodeObj["category"] = entry.Categories.FirstOrDefault();

                    // 效能優化：僅在需要時且針對自定義節點提取埠資訊
                    if (entry is CustomNodeSearchElement customEntry)
                    {
                        ExtractCustomNodePorts(nodeObj, customEntry);
                    }
                }
                
                if (detail == "full")
                {
                    nodeObj["description"] = entry.Description;
                }
                
                globalMatches.Add(nodeObj);
            }

            // 3. Fallback to using Global Index if needed (when no filter or for all scope)
            if (isSearchAll || !string.IsNullOrEmpty(filter))
            {
                BuildGlobalIndex();
                // 這裡可以再補充從索引中快速過濾的邏輯
            }

            // 3. Combine results: Common nodes first, then global nodes
            foreach (var node in commonMatches)
            {
                nodeList.Add(node);
            }
            foreach (var node in globalMatches)
            {
                nodeList.Add(node);
            }

            result["nodes"] = nodeList;
            result["count"] = nodeList.Count;
            result["commonCount"] = commonMatches.Count;
            result["globalCount"] = globalMatches.Count;
            
            if (nodeList.Count >= maxResults)
            {
                result["warning"] = "Result truncated. Please refine search or use 'all' scope.";
            }

            string jsonResult = result.ToString();
            
            // Update cache
            _searchCache[cacheKey] = jsonResult;
            _cacheTime = DateTime.Now;

            MCPLogger.Info($"ListNodes: filter='{filter}', scope={scope}, detail={detail}, results={nodeList.Count} (common={commonMatches.Count}, global={globalMatches.Count})");
            
            return jsonResult;
        }

        private void LoadCommonNodesCache()
        {
            _commonNodesCache = new List<JObject>();
            
            // Try multiple possible paths
            string assemblyDir = System.IO.Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location);
            string[] possiblePaths = new[] {
                System.IO.Path.Combine(assemblyDir, MCPConfig.COMMON_NODES_FILE),
                System.IO.Path.Combine(assemblyDir, "..", MCPConfig.COMMON_NODES_FILE),
                System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), 
                                       "Dynamo", "MCP", MCPConfig.COMMON_NODES_FILE)
            };
            
            foreach (var path in possiblePaths)
            {
                if (System.IO.File.Exists(path))
                {
                    try 
                    {
                        var jsonContent = System.IO.File.ReadAllText(path);
                        var commonArr = JArray.Parse(jsonContent);
                        foreach (var item in commonArr)
                        {
                            if (item is JObject obj) _commonNodesCache.Add(obj);
                        }
                        MCPLogger.Info($"Loaded {_commonNodesCache.Count} common nodes from: {path}");
                        return;
                    } 
                    catch (Exception ex) 
                    {
                        MCPLogger.Warning($"Failed to load common nodes from {path}: {ex.Message}");
                    }
                }
            }
            
            MCPLogger.Warning($"Common nodes file not found in any of the expected locations.");
        }

        private JObject CreateNodeObject(JObject sourceNode, string detail, bool isCommon)
        {
            var nodeObj = new JObject();
            nodeObj["name"] = sourceNode["name"];
            nodeObj["fullName"] = sourceNode["fullName"];
            nodeObj["isCommon"] = isCommon;
            
            if (detail == "standard" || detail == "full")
            {
                nodeObj["inputs"] = sourceNode["inputs"];
                nodeObj["outputs"] = sourceNode["outputs"];
            }
            
            if (detail == "full")
            {
                nodeObj["description"] = sourceNode["description"];
            }
            
            return nodeObj;
        }

        private void ExtractCustomNodePorts(JObject nodeObj, CustomNodeSearchElement customEntry)
        {
            try
            {
                // 在 Dynamo 3.0 中，透過 LibraryServices 獲取節點描述
                var descriptors = _vm.Model.LibraryServices.GetAllFunctionDescriptors(customEntry.FullName);
                var descriptor = descriptors.FirstOrDefault();
                
                if (descriptor != null)
                {
                    var inputs = new JArray();
                    foreach (var param in descriptor.Parameters)
                    {
                        inputs.Add(param.Name);
                    }
                    nodeObj["inputs"] = inputs;

                    var outputs = new JArray();
                    // 輸出口在 FunctionDescriptor 中通常在 ReturnParameters 或類似屬性
                    // 這裡先嘗試 Parameters 中標記為輸出的，或者 ReturnType
                    // 如果是多個輸出，通常會有特定的集合。
                    // 為了安全，如果只有一個，我們可以用 ReturnKeys
                    foreach (var key in descriptor.ReturnKeys)
                    {
                        outputs.Add(key);
                    }
                    
                    if (outputs.Count == 0)
                    {
                        string typeName = descriptor.ReturnType.ToString();
                        if (!string.IsNullOrEmpty(typeName) && typeName != "void") 
                        {
                            outputs.Add(typeName);
                        }
                    }

                    nodeObj["outputs"] = outputs;
                    nodeObj["isCustomNode"] = true;
                }
            }
            catch (Exception ex)
            {
                MCPLogger.Debug($"Could not extract metadata for custom node {customEntry.FullName}: {ex.Message}");
            }
        }

        private void CreateNode(JToken n)
        {
            string tempId = n["id"]?.ToString();
            string nodeName = n["name"]?.ToString(); // e.g., "Point.ByCoordinates"
            double x = n["x"]?.ToObject<double>() ?? 0;
            double y = n["y"]?.ToObject<double>() ?? 0;
            
            // Generate a real GUID for Dynamo
            Guid dynamoGuid = Guid.NewGuid();
            
            if (!string.IsNullOrEmpty(tempId))
            {
                _nodeIdMap[tempId] = dynamoGuid;
            }

            // Execute Command to Create Node
            // Note: nodeName must be the internal creation name or standard name
            
            // Resolve common names using the cache (e.g., "Point.ByCoordinates" -> "Autodesk.DesignScript.Geometry.Point.ByCoordinates")
            if (_commonNodesCache == null) LoadCommonNodesCache();
            var commonMatch = _commonNodesCache?.FirstOrDefault(cn => cn["name"]?.ToString() == nodeName);
            if (commonMatch != null)
            {
                string fullName = commonMatch["fullName"]?.ToString();
                if (!string.IsNullOrEmpty(fullName))
                {
                    MCPLogger.Info($"Resolved common node name '{nodeName}' to '{fullName}'");
                    nodeName = fullName;
                }
            }
            else
            {
                // If not in common nodes, try global index
                BuildGlobalIndex();
                if (_globalNodeIndex != null && _globalNodeIndex.TryGetValue(nodeName, out var entry))
                {
                    if (entry is CustomNodeSearchElement customEntry)
                    {
                        // For custom nodes, we MUST use the GUID string for creation
                        nodeName = customEntry.ID.ToString();
                        MCPLogger.Info($"Resolved custom node '{entry.FullName}' to GUID '{nodeName}' for creation.");
                    }
                    else
                    {
                        MCPLogger.Info($"Resolved node name '{nodeName}' via global index to '{entry.FullName}'");
                        nodeName = entry.FullName;
                    }
                }
            }

            if (nodeName == "Number" || nodeName == "Core.Input.Basic.DoubleInput")
            {
                 var cmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, "Code Block", x, y, false, false);
                 _vm.Model.ExecuteCommand(cmd);
                 
                 if (n["value"] != null)
                 {
                     string val = n["value"].ToString();
                     if (!val.EndsWith(";")) val += ";";
                     var updateCmd = new DynamoModel.UpdateModelValueCommand(new List<Guid> { dynamoGuid }, "Code", val);
                     _vm.Model.ExecuteCommand(updateCmd);
                 }
            }
            else
            {
                try {
                    var cmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, nodeName, x, y, false, false);
                    _vm.Model.ExecuteCommand(cmd);
                } catch (Exception ex) {
                    MCPLogger.Error($"Failed to create node '{nodeName}': {ex.Message}");
                    throw; // Rethrow to be caught by HandleCommand
                }
            }
        }

        private void CreateConnection(JToken c)
        {
            string fromId = c["from"]?.ToString();
            string toId = c["to"]?.ToString();
            int fromPort = c["fromPort"]?.ToObject<int>() ?? 0;
            int toPort = c["toPort"]?.ToObject<int>() ?? 0;

            if (_nodeIdMap.ContainsKey(fromId) && _nodeIdMap.ContainsKey(toId))
            {
                Guid startNodeId = _nodeIdMap[fromId];
                Guid endNodeId = _nodeIdMap[toId];

                // Create the connection using the standard Begin/End MakeConnectionCommand pattern
                try 
                {
                    // 1. Begin connection at the source (Output)
                    var beginCmd = new DynamoModel.MakeConnectionCommand(
                        startNodeId, 
                        fromPort, 
                        PortType.Output, 
                        DynamoModel.MakeConnectionCommand.Mode.Begin
                    );
                    _vm.Model.ExecuteCommand(beginCmd);

                    // 2. End connection at the destination (Input)
                    var endCmd = new DynamoModel.MakeConnectionCommand(
                        endNodeId, 
                        toPort, 
                        PortType.Input, 
                        DynamoModel.MakeConnectionCommand.Mode.End
                    );
                    _vm.Model.ExecuteCommand(endCmd);
                }
                catch (Exception)
                {
                    // 忽略連線錯誤
                }
            }
        }
    }
}
