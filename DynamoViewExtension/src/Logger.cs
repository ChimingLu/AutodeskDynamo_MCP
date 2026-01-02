using System;
using System.IO;
using Autodesk.DesignScript.Runtime;

namespace DynamoMCPListener
{
    /// <summary>
    /// 統一的日誌系統
    /// </summary>
    [IsVisibleInDynamoLibrary(false)]
    public static class MCPLogger
    {
        private static readonly object _lockObj = new object();
        
        /// <summary>
        /// 記錄一般資訊
        /// </summary>
        public static void Info(string message)
        {
            Log("INFO", message);
        }
        
        /// <summary>
        /// 記錄警告訊息
        /// </summary>
        public static void Warning(string message)
        {
            Log("WARN", message);
        }
        
        /// <summary>
        /// 記錄錯誤訊息
        /// </summary>
        public static void Error(string message, Exception ex = null)
        {
            string fullMessage = message;
            if (ex != null)
            {
                fullMessage += $"\nException: {ex.GetType().Name}\nMessage: {ex.Message}\nStackTrace: {ex.StackTrace}";
            }
            Log("ERROR", fullMessage);
        }
        
        /// <summary>
        /// 記錄除錯訊息
        /// </summary>
        public static void Debug(string message)
        {
            #if DEBUG
            Log("DEBUG", message);
            #endif
        }
        
        private static void Log(string level, string message)
        {
            try
            {
                lock (_lockObj)
                {
                    string dir = Path.GetDirectoryName(MCPConfig.LOG_FILE_PATH);
                    if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);

                    string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
                    string logEntry = $"[{timestamp}] [{level}] {message}\n";
                    File.AppendAllText(MCPConfig.LOG_FILE_PATH, logEntry);
                }
            }
            catch
            {
                // 靜默失敗，避免日誌系統本身造成問題
            }
        }
        
        /// <summary>
        /// 清除日誌檔案
        /// </summary>
        public static void ClearLog()
        {
            try
            {
                lock (_lockObj)
                {
                    if (File.Exists(MCPConfig.LOG_FILE_PATH))
                    {
                        File.Delete(MCPConfig.LOG_FILE_PATH);
                    }
                }
            }
            catch
            {
                // 靜默失敗
            }
        }
    }
}
