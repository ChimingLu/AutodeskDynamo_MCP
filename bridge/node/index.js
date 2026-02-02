#!/usr/bin/env node

/**
 * Dynamo MCP Server - Stdio Bridge
 * 提供標準 MCP Stdio 介面與 Python WebSocket Manager 之間的橋接
 * 
 * 架構：
 * AI Clients (Gemini CLI/Claude/VS Code/Antigravity)
 *   ↓ Stdio (MCP Protocol)
 * Node.js MCP Server (本檔案)
 *   ↓ WebSocket (ws://localhost:5051)
 * Python WebSocket Manager (server.py)
 *   ↓ WebSocket (Dynamo Extension內部通訊)
 * Dynamo View Extension (C#)
 */

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { CallToolRequestSchema, ListToolsRequestSchema } = require("@modelcontextprotocol/sdk/types.js");
const WebSocket = require("ws");
const { spawn } = require("child_process");
const path = require("path");
const net = require("net");

// 配置
const PYTHON_WS_URL = "ws://127.0.0.1:65296"; // MCP Bridge port
const RECONNECT_INTERVAL = 5000; // 5 seconds
const REQUEST_TIMEOUT = 30000; // 30 seconds
const PYTHON_STARTUP_TIMEOUT = 5000; // 5 seconds to wait for Python server

// MCP Server 實例
const server = new Server(
    {
        name: "dynamo-mcp-server",
        version: "1.0.0",
    },
    {
        capabilities: {
            tools: {},
        },
    }
);

// WebSocket 狀態管理
let wsClient = null;
let isConnected = false;
let pendingRequests = new Map(); // { requestId: { resolve, reject, timer } }
let requestCounter = 0;
let pythonProcess = null; // Python server 子程序

/**
 * 連接至 Python WebSocket Manager
 */
function connectToPython() {
    return new Promise((resolve, reject) => {
        console.error(`[MCP Bridge] Connecting to Python WebSocket Manager at ${PYTHON_WS_URL}...`);

        wsClient = new WebSocket(PYTHON_WS_URL);

        wsClient.on("open", () => {
            console.error("[MCP Bridge] ✅ Connected to Python WebSocket Manager");
            isConnected = true;
            resolve();
        });

        wsClient.on("message", (data) => {
            try {
                const response = JSON.parse(data.toString());
                console.error(`[MCP Bridge] ← Received from Python:`, JSON.stringify(response).substring(0, 200));

                // 處理回應
                if (response.id && pendingRequests.has(response.id)) {
                    const { resolve, timer } = pendingRequests.get(response.id);
                    clearTimeout(timer);
                    pendingRequests.delete(response.id);
                    resolve(response.result);
                }
            } catch (error) {
                console.error("[MCP Bridge] Failed to parse WebSocket message:", error.message);
            }
        });

        wsClient.on("error", (error) => {
            console.error(`[MCP Bridge] ❌ WebSocket error: ${error.message}`);
            isConnected = false;
            reject(error);
        });

        wsClient.on("close", () => {
            console.error("[MCP Bridge] ⚠️  Connection to Python closed");
            isConnected = false;

            // 清理所有待處理的請求
            for (const [requestId, { reject, timer }] of pendingRequests.entries()) {
                clearTimeout(timer);
                reject(new Error("Connection closed"));
            }
            pendingRequests.clear();

            // 自動重連
            setTimeout(() => {
                console.error("[MCP Bridge] Attempting to reconnect...");
                connectToPython().catch(err => {
                    console.error("[MCP Bridge] Reconnection failed:", err.message);
                });
            }, RECONNECT_INTERVAL);
        });
    });
}

/**
 * 透過 WebSocket 向 Python 發送請求
 */
async function sendToPython(method, params) {
    if (!isConnected || !wsClient || wsClient.readyState !== WebSocket.OPEN) {
        throw new Error("Not connected to Python WebSocket Manager");
    }

    const requestId = `req_${++requestCounter}`;
    const request = {
        jsonrpc: "2.0",
        id: requestId,
        method,
        params
    };

    console.error(`[MCP Bridge] → Sending to Python:`, JSON.stringify(request).substring(0, 200));

    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            pendingRequests.delete(requestId);
            reject(new Error(`Request timeout: ${method}`));
        }, REQUEST_TIMEOUT);

        pendingRequests.set(requestId, { resolve, reject, timer });
        wsClient.send(JSON.stringify(request));
    });
}

/**
 * 處理工具列表請求
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
    console.error("[MCP Bridge] 🔧 Received tools/list request");

    try {
        const toolsList = await sendToPython("tools/list", {});
        console.error(`[MCP Bridge] Registered ${toolsList.length || 0} tools`);
        return { tools: toolsList || [] };
    } catch (error) {
        console.error(`[MCP Bridge] ❌ Failed to list tools: ${error.message}`);
        return { tools: [] };
    }
});

/**
 * 處理工具呼叫請求
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const toolName = request.params.name;
    const toolArgs = request.params.arguments || {};

    console.error(`[MCP Bridge] 🛠️  Executing tool: ${toolName}`);
    console.error(`[MCP Bridge] Arguments:`, JSON.stringify(toolArgs, null, 2).substring(0, 300));

    try {
        const result = await sendToPython("tools/call", {
            name: toolName,
            arguments: toolArgs
        });

        console.error(`[MCP Bridge] ✅ Tool executed successfully`);

        return {
            content: [
                {
                    type: "text",
                    text: typeof result === "string" ? result : JSON.stringify(result, null, 2),
                },
            ],
        };
    } catch (error) {
        console.error(`[MCP Bridge] ❌ Tool execution failed: ${error.message}`);

        return {
            content: [
                {
                    type: "text",
                    text: `Error: ${error.message}`,
                },
            ],
            isError: true,
        };
    }
});

/**
 * 檢查埠口是否可用
 */
function isPortAvailable(port) {
    return new Promise((resolve) => {
        const server = net.createServer();
        server.once('error', () => resolve(false));
        server.once('listening', () => {
            server.close();
            resolve(true);
        });
        server.listen(port, '127.0.0.1');
    });
}

/**
 * 啟動 Python Server
 */
async function startPythonServer() {
    console.error("[MCP Bridge] Checking Python server status...");
    
    // 檢查埠口是否已被佔用
    const portAvailable = await isPortAvailable(65296);
    
    if (!portAvailable) {
        console.error("[MCP Bridge] ✅ Port 65296 already in use, assuming server.py is running");
        return true;
    }
    
    console.error("[MCP Bridge] Port 65296 is available, starting Python server...");
    
    // 啟動 Python server
    const launcherPath = path.join(__dirname, '..', 'launcher.py');
    
    pythonProcess = spawn('python', [launcherPath], {
        cwd: path.join(__dirname, '..', '..'),
        stdio: ['ignore', 'pipe', 'pipe']
    });
    
    // 將 Python 輸出重定向到 stderr
    pythonProcess.stdout.on('data', (data) => {
        console.error(`[Python] ${data.toString().trim()}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python] ${data.toString().trim()}`);
    });
    
    pythonProcess.on('error', (error) => {
        console.error(`[MCP Bridge] ❌ Failed to start Python server: ${error.message}`);
    });
    
    pythonProcess.on('exit', (code) => {
        console.error(`[MCP Bridge] Python server exited with code ${code}`);
        pythonProcess = null;
    });
    
    console.error(`[MCP Bridge] ✅ Python server started (PID: ${pythonProcess.pid})`);
    
    // 等待 Python server 啟動
    console.error("[MCP Bridge] Waiting for Python server to be ready...");
    await new Promise(resolve => setTimeout(resolve, PYTHON_STARTUP_TIMEOUT));
    
    return true;
}

/**
 * 啟動 MCP Server
 */
async function main() {
    console.error("═══════════════════════════════════════════");
    console.error("  Dynamo MCP Server - Stdio Bridge");
    console.error("═══════════════════════════════════════════");
    console.error("");

    try {
        // 啟動 Python Server
        await startPythonServer();
        
        // 連接至 Python WebSocket Manager
        await connectToPython();

        // 啟動 Stdio MCP Server
        const transport = new StdioServerTransport();
        await server.connect(transport);

        console.error("[MCP Bridge] ✅ MCP Server ready for Stdio connections");
        console.error("[MCP Bridge] Waiting for AI client requests...");
        console.error("");
    } catch (error) {
        console.error(`[MCP Bridge] ❌ Startup failed: ${error.message}`);
        process.exit(1);
    }
}

// 錯誤處理
process.on("unhandledRejection", (error) => {
    console.error("[MCP Bridge] Unhandled rejection:", error);
});

process.on("SIGINT", () => {
    console.error("\n[MCP Bridge] Shutting down gracefully...");
    if (wsClient) {
        wsClient.close();
    }
    if (pythonProcess) {
        pythonProcess.kill();
    }
    process.exit(0);
});

// 啟動
main().catch((error) => {
    console.error("[MCP Bridge] Fatal error:", error);
    process.exit(1);
});
