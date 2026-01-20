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
using System.Windows.Controls;
using Dynamo.Wpf.Extensions;
using Autodesk.DesignScript.Runtime; // For IsVisibleInDynamoLibrary
using Dynamo.ViewModels;

namespace DynamoMCPListener
{
    [IsVisibleInDynamoLibrary(false)]
    public class ViewExtension : IViewExtension
    {
        private WebSocketClient _wsClient;
        private string _sessionId;
        private ViewLoadedParams _viewLoadedParams;
        private MenuItem _statusItem;
        private MenuItem _connectItem;
        
        public string UniqueId => "A6B8C4D2-E4F1-4321-ABCD-1234567890EF";
        public string Name => "BIM Assistant (MCP)";

        private static void WriteDebugLog(string msg)
        {
            try {
                string tempDir = System.IO.Path.GetTempPath();
                string path = System.IO.Path.Combine(tempDir, "DynamoMCP_Debug.txt");
                System.IO.File.AppendAllText(path, $"[{DateTime.Now:HH:mm:ss}] [Extension] {msg}\n");
            } catch {}
        }

        public ViewExtension()
        {
            _sessionId = Guid.NewGuid().ToString();
        }

        public void Startup(ViewStartupParams p) { }

        public void Loaded(ViewLoadedParams p)
        {
            _viewLoadedParams = p;
            try 
            {
                // Create Menu Item
                var mcpMenu = new MenuItem { Header = "BIM Assistant" };
                
                _connectItem = new MenuItem { Header = "Connect to MCP Server", IsCheckable = true };
                _connectItem.Click += (s, e) => {
                    if (_connectItem.IsChecked)
                        StartConnection();
                    else
                        StopConnection();
                };
                
                var autoConnectItem = new MenuItem { Header = "Auto-Connect on Startup", IsCheckable = true, IsChecked = true };
                
                mcpMenu.Items.Add(_connectItem);
                mcpMenu.Items.Add(autoConnectItem);
                mcpMenu.Items.Add(new Separator());
                
                _statusItem = new MenuItem { Header = "Status: Disconnected", IsEnabled = false };
                mcpMenu.Items.Add(_statusItem);

                // Add to Dynamo Menu - Use AddExtensionMenuItem for maximum compatibility
                p.AddExtensionMenuItem(mcpMenu);

                if (autoConnectItem.IsChecked)
                {
                    _connectItem.IsChecked = true;
                    StartConnection();
                }

                p.DynamoWindow.Closed += (s, e) => Shutdown();
            }
            catch (Exception ex)
            {
                WriteDebugLog($"Error in Loaded: {ex}");
            }
        }

        private void StartConnection()
        {
            try
            {
                if (_wsClient != null) return;

                var viewModel = _viewLoadedParams.DynamoWindow.DataContext as DynamoViewModel;
                if (viewModel == null)
                {
                    WriteDebugLog("Failed to retrieve DynamoViewModel from DynamoWindow.");
                    return;
                }

                _wsClient = new WebSocketClient(viewModel, _sessionId);
                
                // Link UI Update
                var menu = _viewLoadedParams.DynamoWindow.Resources["DynamoMenu"] as Menu;
                _wsClient.ConnectionStatusChanged += (connected) => {
                    _viewLoadedParams.DynamoWindow.Dispatcher.Invoke(() => {
                        // Find status item in the menu
                        // Note: We should probably keep a reference to statusItem or find it.
                        // For simplicity, we'll try to update the menu header directly if we had the reference.
                        // Since statusItem was local to Loaded, we need to make it a field or find it.
                        UpdateStatusUI(connected);
                    });
                };

                _wsClient.StartAsync();
                WriteDebugLog("WebSocket Connection sequence started.");
            }
            catch (Exception ex)
            {
                WriteDebugLog($"StartConnection Failed: {ex}");
            }
        }

        private void StopConnection()
        {
            if (_wsClient != null)
            {
                _wsClient.StopAsync();
                _wsClient = null;
            }
        }

        public void Shutdown()
        {
            StopConnection();
        }

        public void Dispose()
        {
            Shutdown();
        }

        private void UpdateStatusUI(bool connected)
        {
            if (_statusItem != null)
            {
                _statusItem.Header = connected ? "Status: Connected" : "Status: Disconnected";
            }
            if (!connected && _connectItem != null)
            {
                _connectItem.IsChecked = false;
            }
            if (connected && _connectItem != null)
            {
                _connectItem.IsChecked = true;
            }
        }
    }

    /// <summary>
    /// Keep these for backward compatibility or direct script access, but hide from Library.
    /// </summary>
    public static class MCPControls
    {
        private static WebSocketClient _wsClient;

        private static void WriteDebugLog(string msg)
        {
            try {
                string tempDir = System.IO.Path.GetTempPath();
                string path = System.IO.Path.Combine(tempDir, "DynamoMCP_Debug.txt");
                System.IO.File.AppendAllText(path, $"[{DateTime.Now:HH:mm:ss}] [MCPControls] {msg}\n");
            } catch {}
        }

        internal static void SetWSClient(WebSocketClient client)
        {
            _wsClient = client;
        }

        [IsVisibleInDynamoLibrary(false)]
        public static string StartMCPServer()
        {
            if (_wsClient != null)
            {
                _wsClient.StartAsync();
                return "BIM Assistant: Connected.";
            }
            return "Please use the 'BIM Assistant' menu to connect.";
        }

        [IsVisibleInDynamoLibrary(false)]
        public static string StopMCPServer()
        {
            if (_wsClient != null)
            {
                _wsClient.StopAsync();
                return "BIM Assistant: Disconnected.";
            }
            return "No active connection.";
        }
    }
}
