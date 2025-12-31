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
        /// HTTP Server 主機位址
        /// </summary>
        public const string SERVER_HOST = "127.0.0.1";
        
        /// <summary>
        /// HTTP Server 監聽埠號
        /// </summary>
        public const int SERVER_PORT = 5050;
        
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
    }
}
