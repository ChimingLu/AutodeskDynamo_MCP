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
using System.Windows;
using Dynamo.Wpf.Extensions;
using Autodesk.DesignScript.Runtime; // For IsVisibleInDynamoLibrary
using Dynamo.ViewModels;

namespace DynamoMCPListener
{
    [IsVisibleInDynamoLibrary(false)]
    public class ViewExtension : IViewExtension
    {
        private SimpleHttpServer _server;
        
        // Unique ID for the extension (GUI GUID)
        public string UniqueId => "A6B8C4D2-E4F1-4321-ABCD-1234567890EF";
        
        public string Name => "Dynamo MCP Listener";

        static ViewExtension()
        {
             // Try to log as early as possible
             MCPLogger.Info("ViewExtension Static Constructor");
        }

        public ViewExtension()
        {
            MCPLogger.Info("Constructor called");
        }

        public void Startup(ViewStartupParams p) 
        {
            MCPLogger.Info("Startup called");
        }

        public void Loaded(ViewLoadedParams p)
        {
            MCPLogger.Info("Loaded called");
            try 
            {
                // Register window closed event for cleaner shutdown
                p.DynamoWindow.Closed += (s, e) => {
                    MCPLogger.Info("[ViewExtension] Dynamo Window manual closed detected.");
                    Shutdown();
                };

                _server = new SimpleHttpServer(p);
                _server.Start();
                MCPLogger.Info($"Server started on port {MCPConfig.SERVER_PORT}");
                // MessageBox.Show($"MCP Listener Started on Port {MCPConfig.SERVER_PORT}");
            }
            catch (Exception ex)
            {
                MCPLogger.Error($"Error starting server: {ex.Message}", ex);
                MessageBox.Show($"Failed: {ex.Message}");
            }
        }

        public void Shutdown()
        {
            MCPLogger.Info("[ViewExtension] Shutdown called - stopping all MCP servers");
            
            // Stop ViewExtension's auto-started server
            if (_server != null)
            {
                _server.Stop();
                MCPLogger.Info("[ViewExtension] Auto-started server stopped");
                _server = null;
            }
            
            // Stop manually-started server from MCPControls.StartMCPServer node
            MCPControls.StopStaticServer();
        }

        public void Dispose()
        {
            MCPLogger.Info("[ViewExtension] Dispose called");
            Shutdown();
        }
    }

    public static class MCPControls
    {
        private static SimpleHttpServer _staticServer;

        [IsVisibleInDynamoLibrary(true)]
        public static string StartMCPServer()
        {
            var debugLog = new System.Text.StringBuilder();
            debugLog.AppendLine("Searching for Dynamo Window...");

            try
            {
                var windows = System.Windows.Application.Current.Windows;
                debugLog.AppendLine($"Found {windows.Count} windows in Application.Current.");

                foreach (System.Windows.Window win in windows)
                {
                    string title = "<no title>";
                    try { title = win.Title; } catch {}
                    
                    string typeName = win.GetType().Name;
                    string dcType = "null";
                    if (win.DataContext != null) dcType = win.DataContext.GetType().Name;

                    debugLog.AppendLine($"Win: {title} | Type: {typeName} | DC: {dcType}");

                    // Check 1: DataContext is DynamoViewModel (Relaxed check)
                    if (win.DataContext != null && dcType.Contains("DynamoViewModel"))
                    {
                        var vm = win.DataContext as DynamoViewModel;
                        if (vm != null)
                        {
                            return StartServerWithVM(vm, win.Dispatcher);
                        }
                        else
                        {
                            debugLog.AppendLine("-> Match found but cast to DynamoViewModel failed. Likely version mismatch.");
                            // Try using dynamic/reflection if cast fails? 
                            // For now, just log it.
                        }
                    }
                    
                    // Check 2: Window is DynamoView and has DataContext (Relaxed check)
                    if (typeName.Contains("DynamoView") && win.DataContext != null)
                    {
                         // Modified: DynamoRevitViewModel does not contain "DynamoViewModel" string directly.
                         // So we check if it looks like a Dynamo VM.
                         if (dcType.Contains("Dynamo") && dcType.Contains("ViewModel"))
                         {
                             var vm = win.DataContext as DynamoViewModel;
                             if (vm != null)
                             {
                                 return StartServerWithVM(vm, win.Dispatcher);
                             }
                             else
                             {
                                 debugLog.AppendLine($"-> Match found (DynamoView) with DC {dcType}, but cast to DynamoViewModel failed.");
                             }
                         }
                    }
                }
                
                return $"Failed. Debug Info:\n{debugLog.ToString()}";
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}\nLog:\n{debugLog.ToString()}";
            }
        }

        private static string StartServerWithVM(DynamoViewModel vm, System.Windows.Threading.Dispatcher dispatcher)
        {
            if (vm == null) return "Error: ViewModel is null during start.";

            if (_staticServer == null)
            {
                _staticServer = new SimpleHttpServer(vm, dispatcher);
                _staticServer.Start();
                MCPLogger.Info("[StartMCPServer] Static server started on Port 5050");
                return "MCP Server Started Successfully on Port 5050";
            }
            else
            {
                MCPLogger.Info("[StartMCPServer] Server already running, skipping");
                return "MCP Server is already running";
            }
        }
        
        [IsVisibleInDynamoLibrary(true)]
        public static string StopMCPServer()
        {
            return StopStaticServer();
        }
        
        internal static string StopStaticServer()
        {
            if (_staticServer != null)
            {
                _staticServer.Stop();
                _staticServer = null;
                MCPLogger.Info("[StopMCPServer] Static server stopped and cleaned up");
                return "MCP Server stopped successfully";
            }
            else
            {
                MCPLogger.Info("[StopMCPServer] No server running");
                return "No MCP Server is currently running";
            }
        }
    }


}
