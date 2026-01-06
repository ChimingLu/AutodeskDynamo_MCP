# Autodesk Dynamo MCP Integration Project

這是一個將 **Autodesk Dynamo** 透過 **Model Context Protocol (MCP)** 連接至 AI (如 Claude Desktop) 的核心整合專案。
透過此系統，AI 可以直接控制 Dynamo 進行 BIM 自動化操作，實現「零干預」的自動化建模與查詢。

---

## 🚀 重大更新：自動啟動與中心化管理

1.  **連線管理**：雖然 View Extension 具備自動啟動功能，但為了確保連線穩定性與權限正確，**強烈建議**您在畫板中手動放置 `MCPControls.StartMCPServer` 節點。
2.  **中心化設定 (`mcp_config.json`)**：全域路徑與使用者資訊由設定檔統一管理，確保腳本、範例與測試檔案存放有序且邏輯一致。

---

## 🏗️ 系統架構

1.  **MCP Server (`server.py`)**:
    - 使用 Python (`FastMCP`) 建立，負責將 AI 自然語言指令轉換為 Dynamo 指令。
    - **動態設定**：啟動時自動讀取 `mcp_config.json` 定位資源路徑。
    - **連線偵測**：能在發送前主動檢查 Dynamo 監聽器是否正常運作。

2.  **Dynamo Extension (`DynamoViewExtension/`)**:
    - C# 開發，具備自動載入功能。
    - 接收 JSON 指令並透過 `GraphHandler` 呼叫 Dynamo API。
    - **連線強韌化 (v2.3)**：實作「強制奪取 (Force Takeover)」機制與視窗生命週期（Window.Closed）自動清理功能，有效解決 Revit 多視窗環境下的連線鎖死問題。

3.  **MCP Client**:
    - **Claude Desktop / AI Agent**: 透過設定檔整合 `server.py`。
    - **自動化測試**: 位於 `tests/` 資料夾下的各種功能驗證工具。

---

## 📂 專案結構

- `mcp_config.json`: **[核心設定]** 管理使用者、路徑規則與部屬步驟。
- `server.py`: 主要的 MCP 伺服器，定義 AI 調用的工具集 (Tools)。
- `DynamoViewExtension/`: C# 原始碼，包含 `common_nodes.json` (節點簽名定義)。
- `DynamoScripts/`: 腳本庫，存放經過測試的常用 Dynamo JSON 圖表定義。
- `tests/`: 放置所有驗證、效能測試、功能檢查等 Python 腳本。
- `examples/`: 提供給開發者的基準範例。
- `deploy.ps1`: **[一鍵部署]** 編譯並安裝插件至 Dynamo 套件路徑。
- **`MCP_GUIDELINES.md`**: **[AI 必讀]** 完整的操作規範與節點創建方法。
- **`QUICK_REFERENCE.md`**: **[快速參考]** 常用範例與故障排除指南。

---

## 🛠️ 安裝與部署

1.  **環境需求**:
    - **.NET 8 SDK**。
    - **Revit 2024+** 或 **Dynamo Sandbox 3.x**。
2.  **執行部署**:
    - 完全關閉 Revit 與 Dynamo。
    - 在專案目錄執行：`.\deploy.ps1`
    - 腳本會自動將插件安裝至您的 `%AppData%` 套件資料夾。

---

## 🔥 核心操作工具 (AI Tools)

| 工具名稱 | 功能說明 | 應用情境 |
|---------|---------|----------|
| `execute_dynamo_instructions` | 在畫板放置節點與連線 | 核心自動化建模 |
| `clear_workspace` | **[NEW]** 一鍵清空畫板 | 改版或重新繪製 |
| `analyze_workspace` | 查詢目前節點狀態與錯誤 | Debug 與狀態檢查 |
| `list_available_nodes` | 搜尋 Dynamo 可用節點 (含 .dyf) | 尋找建模工具 |
| `save/load_script_to_library` | 持久化快照腳本至腳本庫 | 模組化復用 |

> [!TIP]
> **防止重疊功能**：執行 `execute_dynamo_instructions` 時，可設定 `clear_before_execute=True`，系統會在繪製新幾何前自動清空畫板。

> [!IMPORTANT]
> **確保連線穩定**：請務必在 Dynamo 畫板中放置 `MCPControls.StartMCPServer` 節點。這能確保 HTTP 伺服器在正確的 Context 下運作，避免因自動啟動機制被回收或權限不足導致的連線中斷。

---

## 🏥 系統健康檢查

新版本支援健康檢查端點，可即時查詢系統狀態和診斷問題：

**使用範例**:
```python
import urllib.request, json

req = urllib.request.Request(
    "http://127.0.0.1:5050/mcp/",
    data=json.dumps({"action": "health_check"}).encode(),
    headers={'Content-Type': 'application/json'}
)
response = urllib.request.urlopen(req)
health = json.loads(response.read().decode())
print(f"狀態: {health['status']}, 運行時間: {health['uptimeSeconds']}秒")
```

**回應範例**:
```json
{
  "status": "healthy",
  "version": "2.3",
  "sessionId": "abc-123...",
  "processId": 12345,
  "uptimeSeconds": 3600,
  "workspace": {"name": "Home", "nodeCount": 15}
}
```

## 📖 使用與控制 (Claude Desktop)

在 `mcpServers` 設定中加入：
```json
"dynamo-mcp": {
  "command": "python",
  "args": ["絕對路徑/server.py"]
}
```
隨後透過中文指令進行控制，例如：「幫我畫一個 100x100 的長方體，畫之前先清空畫面」。

---

## ⚖️ 權利聲明 (Copyright)
本專案目前為 **私有專案 (Private)**，僅供受邀者進行測試與評估。

Copyright © 2026 ChimingLu. All Rights Reserved.

**未經作者書面許可，嚴禁任何形式的複製、分發、公開傳播或用於商業用途。**
若您對本專案有商業合作或使用需求，請聯繫作者。
