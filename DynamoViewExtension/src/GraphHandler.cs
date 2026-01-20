using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Dynamo.Graph.Nodes;
using Dynamo.Graph.Connectors;
using Dynamo.Models;
using Dynamo.ViewModels;
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
                    // Start of list_nodes implementation
                    string filter = data["filter"]?.ToString() ?? "";
                    // Minimal implementation, can be expanded
                    return "{\"status\": \"ok\", \"nodes\": []}"; 
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
                            string msg = $"[CreateNode Failed] {n["name"]} (ID: {n["id"]}): {ex.Message}";
                            MCPLogger.Error(msg, ex);
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
            // Removed try-catch to allow bubbling to HandleCommand
            string nodeName = n["name"]?.ToString();
            string nodeIdStr = n["id"]?.ToString();
            double x = n["x"]?.ToObject<double>() ?? 0;
            double y = n["y"]?.ToObject<double>() ?? 0;

            MCPLogger.Info($"[CreateNode] 開始創建節點: {nodeName} (ID: {nodeIdStr})");

            Guid dynamoGuid = Guid.TryParse(nodeIdStr, out Guid parsedGuid) ? parsedGuid : Guid.NewGuid();
            
            if (!string.IsNullOrEmpty(nodeIdStr))
            {
                _nodeIdMap[nodeIdStr] = dynamoGuid;
            }

            // === Code Block ===
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

            // === Native Nodes ===
            string finalFullName = nodeName;
            bool isExplicitOverload = false;
            string ovId = n["overload"]?.ToString();

            if (_commonNodesCache == null) LoadCommonNodesCache();
            var commonMatch = _commonNodesCache?.FirstOrDefault(cn => cn["name"]?.ToString() == nodeName);
            
            if (commonMatch != null)
            {
                finalFullName = commonMatch["fullName"]?.ToString();
                if (!string.IsNullOrEmpty(ovId))
                {
                    var overloads = commonMatch["overloads"] as JArray;
                    var target = overloads?.FirstOrDefault(o => o["id"]?.ToString() == ovId);
                    if (target != null)
                    {
                        finalFullName = target["fullName"]?.ToString();
                        isExplicitOverload = true;
                    }
                }
            }

            string creationName = finalFullName;
            if (!isExplicitOverload && creationName.Contains("@") && !Guid.TryParse(creationName, out _))
            {
                creationName = creationName.Split('@')[0];
            }

            MCPLogger.Info($"[CreateNode] Executing CreateNodeCommand: {creationName}");
            var nativeCmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, creationName, x, y, false, false);
            _dynamoModel.ExecuteCommand(nativeCmd);
            
            if (n["value"] != null)
            {
                string propertyName = GetValuePropertyName(creationName);
                if (!string.IsNullOrEmpty(propertyName))
                {
                    var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, propertyName, n["value"].ToString());
                    _dynamoModel.ExecuteCommand(updateCmd);
                }
            }

            HandlePreview(n, dynamoGuid);
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
