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

                // 0. Handle Actions (like clear_graph)
                string action = data["action"]?.ToString();
                if (action == "clear_graph")
                {
                    var nodesToDelete = _dynamoModel.CurrentWorkspace.Nodes.Select(n => n.GUID).ToList();
                    if (nodesToDelete.Any())
                    {
                        _dynamoModel.ExecuteCommand(new DynamoModel.DeleteModelCommand(nodesToDelete));
                    }
                    _nodeIdMap.Clear(); // 清空映射表
                    MCPLogger.Info("[GraphHandler] Workspace cleared via DeleteModelCommand.");
                    return "{\"status\": \"ok\", \"message\": \"Workspace cleared\"}";
                }

                if (action == "get_graph_status")
                {
                    var nodes = _dynamoModel.CurrentWorkspace.Nodes.Select(n => new
                    {
                        id = n.GUID.ToString(),
                        name = n.Name, // Use Name (which might vary) or CreationName? StartMCPServer usually has a specific Title/Name.
                        // For CustomNodes/StartMCPServer, Name might be "StartMCPServer" or "MCPControls.StartMCPServer".
                        // Better to include both if possible, or just Name and let python check. 
                        // Python checks: node.get("name") == "MCPControls.StartMCPServer"
                        // In Dynamo, Custom Node name might be just "StartMCPServer". 
                        // Let's verify what Name returns for the node.
                        // Actually, let's also return typical position info.
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
                }
                
                // 1. Create Nodes
                if (data["nodes"] != null)
                {
                    foreach (var n in data["nodes"])
                    {
                        CreateNode(n);
                    }
                }

                // 2. Create Connectors
                if (data["connectors"] != null)
                {
                    foreach (var c in data["connectors"])
                    {
                        CreateConnection(c);
                    }
                }
                return "{\"status\": \"ok\"}";
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"Error executing instructions: {ex.Message}");
                return $"{{\"error\": \"{ex.Message}\"}}";
            }
        }

        private void CreateNode(JToken n)
        {
            try
            {
                string nodeName = n["name"]?.ToString();
                string nodeIdStr = n["id"]?.ToString();
                double x = n["x"]?.ToObject<double>() ?? 0;
                double y = n["y"]?.ToObject<double>() ?? 0;

                MCPLogger.Info($"[CreateNode] 開始創建節點: {nodeName} (ID: {nodeIdStr})");

                Guid dynamoGuid = Guid.TryParse(nodeIdStr, out Guid parsedGuid) ? parsedGuid : Guid.NewGuid();
                
                // 記錄字串 ID 與 GUID 的映射
                if (!string.IsNullOrEmpty(nodeIdStr))
                {
                    _nodeIdMap[nodeIdStr] = dynamoGuid;
                    MCPLogger.Info($"[CreateNode] 映射 ID: {nodeIdStr} -> {dynamoGuid}");
                }

                // === 優先處理 Code Block 類型節點 ===
                if (nodeName == "Number" || nodeName == "Code Block")
                {
                    MCPLogger.Info($"[CreateNode] 識別為 Code Block 節點，位置: ({x}, {y})");
                    var cmd = new DynamoModel.CreateNodeCommand(new List<Guid> { dynamoGuid }, "Code Block", x, y, false, false);
                    _dynamoModel.ExecuteCommand(cmd);
                    
                    if (n["value"] != null)
                    {
                        string val = n["value"].ToString();
                        if (!val.EndsWith(";")) val += ";";
                        MCPLogger.Info($"[CreateNode] 設定 Code Block 值: {val}");
                        var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, "Code", val);
                        _dynamoModel.ExecuteCommand(updateCmd);
                    }
                    MCPLogger.Info($"[CreateNode] Code Block 節點創建完成");
                    
                    // 處理預覽狀態
                    if (n["preview"] != null)
                    {
                        bool isPreview = n["preview"].ToObject<bool>();
                        if (!isPreview)
                        {
                            var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, "IsVisible", "false");
                            _dynamoModel.ExecuteCommand(updateCmd);
                            MCPLogger.Info($"[CreateNode] 節點 {dynamoGuid} 預覽已隱藏");
                        }
                    }
                    return; // 提早返回
                }

                // === 處理原生/其他節點 ===
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

                MCPLogger.Info($"[CreateNode] creationName: {creationName}, GUID: {dynamoGuid}");
                MCPLogger.Info($"[CreateNode] 創建原生節點: {creationName}");
                
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

                // 處理預覽狀態
                if (n["preview"] != null)
                {
                    bool isPreview = n["preview"].ToObject<bool>();
                    if (!isPreview)
                    {
                        var updateCmd = new DynamoModel.UpdateModelValueCommand(Guid.Empty, dynamoGuid, "IsVisible", "false");
                        _dynamoModel.ExecuteCommand(updateCmd);
                        MCPLogger.Info($"[CreateNode] 節點 {dynamoGuid} 預覽已隱藏");
                    }
                }
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"Error in CreateNode: {ex.Message}");
                MCPLogger.Error($"StackTrace: {ex.StackTrace}");
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
            try
            {
                string fromIdStr = c["from"]?.ToString();
                string toIdStr = c["to"]?.ToString();
                int fromIdx = c["fromPort"]?.ToObject<int>() ?? 0;
                int toIdx = c["toPort"]?.ToObject<int>() ?? 0;

                MCPLogger.Info($"[CreateConnection] 開始創建連線: {fromIdStr}[{fromIdx}] -> {toIdStr}[{toIdx}]");

                // 嘗試從映射表解析 GUID，如果失敗則直接解析字串
                Guid fromId;
                if (!_nodeIdMap.TryGetValue(fromIdStr, out fromId))
                {
                    fromId = Guid.Parse(fromIdStr); // 如果不在映射表中，嘗試直接解析
                }
                
                Guid toId;
                if (!_nodeIdMap.TryGetValue(toIdStr, out toId))
                {
                    toId = Guid.Parse(toIdStr);
                }
                
                MCPLogger.Info($"[CreateConnection] 解析後的 GUID: {fromId} -> {toId}");

                MCPLogger.Info($"[CreateConnection] 執行 MakeConnectionCommand - Begin");
                _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(fromId, fromIdx, PortType.Output, DynamoModel.MakeConnectionCommand.Mode.Begin));
                
                MCPLogger.Info($"[CreateConnection] 執行 MakeConnectionCommand - End");
                _dynamoModel.ExecuteCommand(new DynamoModel.MakeConnectionCommand(toId, toIdx, PortType.Input, DynamoModel.MakeConnectionCommand.Mode.End));
                
                MCPLogger.Info($"[CreateConnection] 連線創建完成");
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"[CreateConnection] 創建連線失敗: {ex.Message}");
                MCPLogger.Error($"StackTrace: {ex.StackTrace}");
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
            } catch { }
        }
    }
}
