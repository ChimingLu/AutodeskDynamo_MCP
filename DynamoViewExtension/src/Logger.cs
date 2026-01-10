/*
 * Copyright 2026 ChimingLu.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

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
        private const long MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
        private const int MAX_BACKUP_FILES = 3;
        
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

                    // 檢查並執行日誌輪替
                    RotateLogIfNeeded();

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
        /// 日誌輪替：當日誌檔案超過限制時自動備份
        /// </summary>
        private static void RotateLogIfNeeded()
        {
            try
            {
                if (!File.Exists(MCPConfig.LOG_FILE_PATH))
                    return;

                FileInfo logFile = new FileInfo(MCPConfig.LOG_FILE_PATH);
                if (logFile.Length < MAX_LOG_SIZE_BYTES)
                    return;

                // 輪替現有備份檔案（.old.3 -> delete, .old.2 -> .old.3, ...）
                for (int i = MAX_BACKUP_FILES; i >= 1; i--)
                {
                    string oldFile = $"{MCPConfig.LOG_FILE_PATH}.old.{i}";
                    if (i == MAX_BACKUP_FILES)
                    {
                        // 刪除最舊的備份
                        if (File.Exists(oldFile))
                            File.Delete(oldFile);
                    }
                    else
                    {
                        // 往後推移一個編號
                        string nextFile = $"{MCPConfig.LOG_FILE_PATH}.old.{i + 1}";
                        if (File.Exists(oldFile))
                            File.Move(oldFile, nextFile);
                    }
                }

                // 將目前檔案備份為 .old.1
                File.Move(MCPConfig.LOG_FILE_PATH, $"{MCPConfig.LOG_FILE_PATH}.old.1");
            }
            catch
            {
                // 輪替失敗不影響主要日誌功能
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
