# 技術堆疊說明

> **專案**: AutodeskDynamo_MCP  
> **最後更新**: 2026-02-04

---

## 📦 核心技術

| 層級 | 技術 | 版本 | 用途 |
|:---|:---|:---|:---|
| **Extension** | C# / .NET | .NET 8.0 | Dynamo View Extension |
| **Bridge** | Python | 3.11+ | MCP Server 與 WebSocket 管理 |
| **Bridge** | Node.js | 18+ | Stdio-to-WS 橋接器 |
| **Protocol** | WebSocket | RFC 6455 | 持久連線通訊 |
| **Protocol** | MCP | 1.0 | AI 工具調用標準 |

---

## 🔗 架構圖

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Client     │────▶│  Bridge Server  │────▶│ Dynamo Extension│
│ (VSCode/Claude) │     │  (Python + Node)│     │     (C#)        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │ MCP Protocol          │ WebSocket             │ Dynamo API
        │ (Stdio)               │ (ws://65296)          │ (Internal)
        ▼                       ▼                       ▼
   Tool Calls              Session Mgmt            Node Creation
```

---

## 📁 關鍵檔案位置

| 檔案 | 路徑 | 說明 |
|:---|:---|:---|
| MCP Server | `bridge/python/server.py` | 主要 MCP 處理器 |
| WebSocket Bridge | `bridge/node/index.js` | Stdio-to-WS 轉換 |
| Extension Entry | `DynamoViewExtension/src/DynamoViewExtension.cs` | Extension 入口 |
| Graph Handler | `DynamoViewExtension/src/GraphHandler.cs` | 節點操作核心 |
| Node Metadata | `DynamoViewExtension/common_nodes.json` | 節點簽名定義 |
| Config | `mcp_config.json` | 中心化配置 |

---

## 🔧 開發環境

### 必要條件
- **Dynamo**: 3.0+ (建議 3.3)
- **Visual Studio**: 2022+
- **Python**: 3.11+
- **Node.js**: 18+

### 安裝指令
```powershell
# 一鍵部署
.\deploy.ps1

# 僅安裝相依套件
pip install -r requirements.txt
```

---

## 📡 通訊端口

| 端口 | 用途 | 說明 |
|:---|:---|:---|
| `65296` | Bridge Server | Python MCP Server 監聽 |
| `65535` | Dynamo WS | Extension WebSocket 端點 |

---

## ⚠️ 已知限制

1. **單機模式**: 目前僅支援本機通訊 (localhost)
2. **Dynamo 版本**: 2.x 的 Python 節點名稱不同，需使用 Name Loop
3. **Windows Only**: Extension 僅在 Windows 上測試
