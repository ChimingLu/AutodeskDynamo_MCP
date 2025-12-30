# Autodesk Dynamo MCP Integration Project

這是一個將 **Autodesk Dynamo** 透過 **Model Context Protocol (MCP)** 連接至 AI (如 Claude Desktop) 的整合專案。
透過此系統，AI 可以直接控制 Dynamo 進行 BIM 自動化操作，例如放置節點、連接線路、查詢參數等。

## 系統架構

1.  **MCP Server (`server.py`)**:
    - 使用 Python (`mcp`) 建立的 MCP 伺服器。
    - 負責接收來自 AI 客戶端的自然語言指令，並轉換為 Dynamo 可執行的 JSON 指令。
    - 透過 HTTP (預設 Port 5050) 與 Dynamo View Extension 通訊。

2.  **Dynamo Extension (`DynamoViewExtension/`)**:
    - 使用 C# 開發的 Dynamo View Extension。
    - 包含 `DynamoMCPListener` 控制器，啟動後在 Port 5050 監聽 POST 請求。
    - 接收 JSON 指令並透過 `GraphHandler` 呼叫 Dynamo API 建立節點與連線。

3.  **MCP Client**:
    - **Claude Desktop**: 透過設定檔連接 `server.py`，實現自然語言對話控制。
    - **測試工具**: 如 `run_lib_test.py` 用於自動化測試腳本執行。

---

## 專案結構

- `server.py`: 主要的 MCP Python 伺服器，定義了與 AI 互動的工具 (Tools)。
- `DynamoViewExtension/`: C# 專案原始碼，包含 Dynamo 插件的邏輯。
    - `src/`: 核心程式碼 (Extension, GraphHandler, Logger 等)。
    - `common_nodes.json`: 常用節點的詳細簽名定義，協助 AI 精確辨識節點。
- `DynamoScripts/`: JSON 腳本庫，存放經過測試的常用 Dynamo 圖表定義。
- `MCP_Listener_Package/`: Dynamo 套件配置檔案。
- `deploy.ps1`: **[自動化部署腳本]** 一鍵編譯 C# 專案並安裝到 Dynamo 套件路徑。
- `*.py (測試專案)`: `performance_test.py`, `run_lib_test.py` 等用於驗證系統功能的腳本。

---

## 安裝與部署

本專案提供 PowerShell 自動化腳本，可自動編譯並安裝至現有的 Dynamo 環境。

1.  **環境需求**:
    - 安裝 **.NET 8 SDK**。
    - 建議環境為 **Revit 2024+** 或 **Dynamo Sandbox 3.x**。
2.  **執行部署**:
    - **💡 重要**: 執行前請務必**完全關閉 Revit 與 Dynamo**，避免檔案鎖定。
    - 以管理員或一般權限執行：
      ```powershell
      .\deploy.ps1
      ```
    - 腳本會自動將編譯後的 DLL 與配置檔案複製到 Dynamo 的 Packages 資料夾。

---

## 啟動與使用

### 1. 啟動 Dynamo Listener
1. 開啟 **Revit** (或 Dynamo Sandbox)。
2. 開啟 **Dynamo** 介面。
3. 插件會隨 Dynamo 啟動自動加載。若成功啟動，會出現彈出視窗提示：`MCP Server Started Successfully on Port 5050`。

### 2. 啟動 Python MCP Server
1. 在專案根目錄開啟終端機。
2. 啟動伺服器：
    ```bash
    python server.py
    ```
3. 此伺服器將作為 AI 的橋樑，等待指令調用。

### 3. AI 控制 (Claude Desktop)
在 Claude Desktop 的 `mcpServers` 設定中加入：
```json
"dynamo-mcp": {
  "command": "python",
  "args": ["絕對路徑/server.py"]
}
```
隨後即可用中文指令控制，例如：「在 Dynamo 中建立一個點，座標為 (50, 50, 0)」。

---

## 腳本庫清單 (DynamoScripts)

目前腳本庫中已包含以下預建功能，AI 可透過 `get_script_library` 工具查詢並直接執行：

| 腳本名稱 | 功能說明 | 核心用途 |
|---------|---------|----------|
| `point_basic` | 建立多組基礎座標點 | 點選取與幾何測試 |
| `point_custom` | 帶有自訂座標配置的點 | 參數化點建立 |
| `line_basic` | 建立起點與終點並連接成線 | 基礎線段幾何 |
| `line_simple` | 簡化版線段連線邏輯 | 快速連線範例 |
| `simple_line` | 極簡化線段測試 | 回歸測試 |
| `random_line` | 產生隨機座標的線條 | 動態生成測試 |
| `connect_points` | 設定兩個點並嘗試連線 | 邏輯連接測試 |
| `solid_demo` | 建立簡單的 3D 立體幾何 | 空間實體範例 |
| `number` | 建立純數值輸入節點 | 數據輸入範例 |

---

## 操作指南

### 擴充基礎節點支援
若 AI 無法正確辨識某些複雜節點 (Overload 問題)，可修改 `DynamoViewExtension/common_nodes.json` 增加特定簽名定義。

### 效能與 Token 優化
本專案針對 AI 通訊進行了優化：
- **分層查詢**: `get_all_nodes` 支援 `basic`, `standard`, `full` 三種細節等級，減少 70% 以上的無效 Token 消耗。
- **快取機制**: 緩存 Dynamo 節點清單，提升工具回應速度。

---

## 授權
本專案採用 **MIT License**。詳見 [LICENSE](LICENSE) 檔案。
