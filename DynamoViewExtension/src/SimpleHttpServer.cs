using System;
using System.IO;
using System.Net;
using System.Threading.Tasks;
using System.Windows;
using Dynamo.Wpf.Extensions;
using Dynamo.ViewModels;
using Autodesk.DesignScript.Runtime;

namespace DynamoMCPListener
{
    [IsVisibleInDynamoLibrary(false)]
    public class SimpleHttpServer
    {
        // Global tracker for takeover logic
        private static SimpleHttpServer _currentInstance;
        private static readonly object _instanceLock = new object();

        public readonly string InstanceSessionId = Guid.NewGuid().ToString();
        private HttpListener _listener;
        private ViewLoadedParams _dynamoParams;
        private bool _isRunning = false;
        private System.Windows.Threading.Dispatcher _dispatcher;
        private GraphHandler _handler;

        public SimpleHttpServer(ViewLoadedParams p)
        {
            _dynamoParams = p;
            if (p.DynamoWindow.DataContext is DynamoViewModel vm) _handler = new GraphHandler(vm, InstanceSessionId);
            _dispatcher = p.DynamoWindow.Dispatcher;
            _listener = new HttpListener();
            _listener.Prefixes.Add(MCPConfig.ServerUrl);
        }

        public SimpleHttpServer(DynamoViewModel vm, System.Windows.Threading.Dispatcher dispatcher)
        {
            _handler = new GraphHandler(vm, InstanceSessionId);
            _dispatcher = dispatcher;
            _listener = new HttpListener();
            _listener.Prefixes.Add(MCPConfig.ServerUrl);
        }

        public void Start()
        {
            if (_isRunning) return;

            lock (_instanceLock)
            {
                // FORCE TAKEOVER: Stop any existing instance in the same process
                if (_currentInstance != null)
                {
                    try {
                        MCPLogger.Info($"[SimpleHttpServer] Force Takeover: Stopping old instance {_currentInstance.InstanceSessionId}");
                        _currentInstance.Stop();
                    } catch (Exception ex) {
                        MCPLogger.Error($"[SimpleHttpServer] Error stopping old instance: {ex.Message}");
                    }
                }
                
                try {
                    _listener.Start();
                    _isRunning = true;
                    _currentInstance = this;
                    Task.Run(() => ListenLoop());
                    MCPLogger.Info($"[SimpleHttpServer] Instance started: {InstanceSessionId}");
                } catch (Exception ex) {
                    MCPLogger.Error($"[SimpleHttpServer] Failed to start listener: {ex.Message}");
                }
            }
        }

        public void Stop()
        {
            _isRunning = false;
            if (_listener.IsListening)
                _listener.Stop();
        }

        private async Task ListenLoop()
        {
            while (_isRunning)
            {
                try
                {
                    var context = await _listener.GetContextAsync();
                    // Process in background, but Handler will Dispatch to UI
                    ProcessRequest(context); 
                }
                catch (HttpListenerException) { break; }
                catch (ObjectDisposedException) { break; }
                catch (Exception) { 
                    // Log error?
                }
            }
        }

        private void ProcessRequest(HttpListenerContext context)
        {
            string responseString = "{\"status\": \"ok\"}";
            int statusCode = 200;

            try
            {
                if (context.Request.HttpMethod == "POST")
                {
                    using (var reader = new StreamReader(context.Request.InputStream, context.Request.ContentEncoding))
                    {
                        string jsonLine = reader.ReadToEnd();
                        
                        // Dispatch the work to the UI thread because we touch Dynamo Model
                        _dispatcher.Invoke(() => {
                            try {
                                responseString = _handler.HandleCommand(jsonLine);
                            } catch (Exception ex) {
                                // Modified: Return error to client instead of blocking UI with MessageBox
                                statusCode = 500;
                                responseString = $"{{\"error\": \"Execution error: {ex.Message}\"}}";
                            }
                        });
                        
                        // Note: Because Invoke is synchronous, we can capture the result/error if we refactored slightly.
                        // But here 'responseString' is local to ProcessRequest, and the Invoke above is a lambda.
                        // The lambda cannot easily write back to 'responseString' variable of the outer scope 
                        // unless we use a closure variable that is thread-safe or simply wait.
                        // Actually, 'Invoke' blocks until done. So we CAN set a variable.
                    }
                }
            }
            catch (Exception ex)
            {
                statusCode = 500;
                responseString = $"{{\"error\": \"Server error: {ex.Message}\"}}";
            }
            finally
            {
                // If we want to return the inner error from the UI thread, we need to capture it.
                // For now, let's keep it simple: If UI thread fails silent (no MessageBox), 
                // we might return "ok" which is misleading.
                // Better approach:
            }
            
            // Let's refine the logic to truly capture the error from UI thread.
            // But for this quick fix, removing MessageBox is the priority.
            {
                byte[] buffer = System.Text.Encoding.UTF8.GetBytes(responseString);
                context.Response.ContentLength64 = buffer.Length;
                context.Response.StatusCode = statusCode;
                context.Response.OutputStream.Write(buffer, 0, buffer.Length);
                context.Response.OutputStream.Close();
            }
        }
    }
}
