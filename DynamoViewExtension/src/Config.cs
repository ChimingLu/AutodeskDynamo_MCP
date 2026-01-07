using Autodesk.DesignScript.Runtime;

namespace DynamoMCPListener
{
    /// <summary>
    /// 統一管理 MCP Server 的設定參數
    /// </summary>
    [IsVisibleInDynamoLibrary(false)]
    public static class MCPConfig
    {
        /// <summary>
        /// HTTP Server 主機位址 (Default)
        /// </summary>
        public static string SERVER_HOST = "127.0.0.1";
        
        /// <summary>
        /// HTTP Server 監聽埠號 (Default)
        /// </summary>
        public static int SERVER_PORT = 5050; // Will be overwritten by LoadConfig
        
        /// <summary>
        /// HTTP Server 路徑
        /// </summary>
        public const string SERVER_PATH = "/mcp/";
        
        /// <summary>
        /// 完整的 Server URL
        /// </summary>
        public static string ServerUrl => $"http://{SERVER_HOST}:{SERVER_PORT}{SERVER_PATH}";
        
        /// <summary>
        /// 日誌檔案路徑
        /// </summary>
        public static string LOG_FILE_PATH => System.IO.Path.Combine(
            System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData), 
            "Dynamo", "MCP", "DynamoMCP.log");
        
        /// <summary>
        /// Common Nodes 檔案名稱
        /// </summary>
        public const string COMMON_NODES_FILE = "common_nodes.json";
        
        /// <summary>
        /// 節點快取有效期限 (分鐘)
        /// </summary>
        public const int CACHE_EXPIRY_MINUTES = 5;
        
        /// <summary>
        /// 預設搜尋範圍的最大結果數
        /// </summary>
        public const int DEFAULT_MAX_RESULTS = 20;
        
        /// <summary>
        /// 全域搜尋範圍的最大結果數
        /// </summary>
        public const int ALL_SCOPE_MAX_RESULTS = 200;

        static MCPConfig()
        {
            LoadConfig();
        }

        private static void LoadConfig()
        {
            try 
            {
                // Config file is expected to be in the same directory as the assembly (the package root/bin or root)
                // Since this DLL is in bin, and we deploy config to the package root, we need to look up.
                // However, our deploy script puts everything in TargetPackageDir.
                // The DLL is loaded from TargetPackageDir/bin/DynamoMCPListener.dll
                
                string assemblyLocation = System.Reflection.Assembly.GetExecutingAssembly().Location;
                string packageRoot = System.IO.Path.GetDirectoryName(System.IO.Path.GetDirectoryName(assemblyLocation));
                string configPath = System.IO.Path.Combine(packageRoot, "mcp_config.json");

                if (!System.IO.File.Exists(configPath))
                {
                    // Fallback to bin dir if deployed flat
                    configPath = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(assemblyLocation), "mcp_config.json");
                }

                if (System.IO.File.Exists(configPath))
                {
                    string json = System.IO.File.ReadAllText(configPath);
                    // Minimal manual parsing to avoid heavy dependencies if possible, 
                    // but we can use Newtonsoft.Json as Dynamo has it.
                    var jobj = Newtonsoft.Json.Linq.JObject.Parse(json);
                    
                    if (jobj["server"] != null)
                    {
                        var serverParams = jobj["server"];
                        if (serverParams["host"] != null) SERVER_HOST = serverParams["host"].ToString();
                        if (serverParams["port"] != null) SERVER_PORT = serverParams["port"].ToObject<int>();
                    }
                }
            }
            catch (System.Exception)
            {
                // Ignore errors and use defaults
            }
        }
    }
}
