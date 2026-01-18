**語言 / Language:** [繁體中文](README.md) | [English](README_EN.md)

---

# Autodesk Dynamo MCP Integration Project

這是一個將 **Autodesk Dynamo** 透過 **Model Context Protocol (MCP)** 連接至 AI (如 Antigravity) 的核心整合專案。
透過此系統，AI 可以直接控制 Dynamo 進行 BIM 自動化操作，實現「零干預」的自動化建模與查詢。

---

## 🚀 重大更新：自動啟動與中心化管理

1.  **連線管理**：雖然 View Extension 具備自動啟動功能，但為了確保連線穩定性與權限正確，**強烈建議**您在畫板中手動放置 `MCPControls.StartMCPServer` 節點。
2.  **中心化設定 (`mcp_config.json`)**：全域路徑與使用者資訊由設定檔統一管理，確保腳本、範例與測試檔案存放有序且邏輯一致。


> [!CRITICAL]
> **重啟 Dynamo 前注意事項**：若需關閉或重啟 Dynamo，**請務必先停止 Python Server (Ctrl+C)**。否則舊的連線會被 Python 端佔用，導致新的 Dynamo 無法綁定連接埠，產生「連線超時」或「殭屍連線」錯誤。

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

- **`mcp_config.template.jsonc`**: **[配置模板]** 帶繁體中文註解的配置範本，使用者應編輯此檔案。
- **`mcp_config.json`**: **[自動生成]** 由模板轉換的純 JSON 設定檔，程式讀取使用（請勿手動編輯）。
- `docs/CONFIG_GUIDE.md`: **[配置指南]** 詳細說明如何修改配置檔案。
- `server.py`: 主要的 MCP 伺服器，定義 AI 調用的工具集 (Tools)。
- `DynamoViewExtension/`: C# 原始碼，包含 `common_nodes.json` (節點簽名定義)。
- `DynamoScripts/`: 腳本庫，存放經過測試的常用 Dynamo JSON 圖表定義。
- **`domain/`**: **[SOP 知識庫]** 標準操作程序與故障排除指南。
  - `startup_checklist.md`: 啟動檢查清單（AI 初始化必讀）
  - `troubleshooting.md`: 完整故障排除流程
  - `node_creation_strategy.md`: **[NEW]** 雙軌節點創建策略完整技術指南（決策樹 + 實戰案例）
  - `architecture_analysis.md`: **[NEW]** 架構衝突診斷報告與雙軌制改善方案
  - `visual_analysis_workflow.md`: `/image` 指令的標準執行流程
- `tests/`: 放置所有驗證、效能測試、功能檢查等 Python 腳本。**（此效用目錄被 Git 忽略，腳本不會上傳）**
- `examples/`: 提供給開發者的基準範例。
- `image/`: **[視覺化產出]** 存放 `/image` 指令產出的腳本分析圖表與技術文檔。**（此產出目錄被 Git 忽略，圖片不會上傳）**
- `deploy.ps1`: **[一鍵部署]** 編譯並安裝插件至 Dynamo 套件路徑。
- **`GEMINI.md`**: **[AI 必讀]** 完整的操作規範與節點創建方法。
- **`QUICK_REFERENCE.md`**: **[快速參考]** 常用範例與故障排除指南。

---

## 🛠️ 安裝與部署

1.  **環境需求**:
    - **.NET 8 SDK**。
    - **Revit 2025** + **Dynamo 3.3**（或相容版本）。
2.  **配置設定**（首次使用）:
    - 編輯 `mcp_config.template.jsonc`，修改標記為 🔧 的項目（如使用者名稱、伺服器埠號）。
    - 詳細說明請參考 [`docs/CONFIG_GUIDE.md`](docs/CONFIG_GUIDE.md)。
3.  **執行部署**:
    - 完全關閉 Revit 與 Dynamo。
    - 在專案目錄執行：`.\deploy.ps1`
    - 腳本會自動：
      1. 將模板轉換為 `mcp_config.json`
      2. 建置 C# 專案
      3. 安裝插件至 `%AppData%` 套件資料夾

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

## 📖 使用與控制 (Clients)

### 1. Antigravity / Gemini CLI
在 Antigravity 的 MCP 設定中加入：
```json
"dynamo-mcp": {
  "command": "python",
  "args": ["絕對路徑/server.py"]
}
```

### 2. Claude Desktop (推薦)
點擊 Claude Desktop 設定中的 "Edit Config" 按鈕，加入以下內容：
> **注意**：必須使用 `python` 指令，且路徑請使用 **絕對路徑** (e.g. `D:\\...`)。

```json
"dynamo-mcp": {
  "command": "python",
  "args": [
    "絕對路徑\\server.py"
  ]
}
```
設定完成後，Claude 列表中會出現 `dynamo-mcp` (綠燈)，即可開始使用。

---

## ⚖️ 權利聲明 (License)

Copyright 2026 ChimingLu.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
