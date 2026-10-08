# Dynamo MCP 快速參考手冊 (Quick Reference)

## 📌 核心連線資訊
- **MCP Bridge (Node.js)**: `ws://127.0.0.1:65296` (用於 MCP 客戶端連線)
- **Dynamo WebSocket**: `ws://127.0.0.1:65535` (C# Extension 專用連線)
- **關鍵操作庫**: `bridge/python/server.py` (主要調度器)
- **控制介面**:
    - `BIM Assistant Menu`: 透過選單控制 WebSocket 監聽。
    - `Connect to MCP Server`: 點擊手動連線。

---

## 🎨 節點創建策略

> **完整技術指南**：[`domain/node_creation_strategy.md`](domain/node_creation_strategy.md)

### 選擇正確的方案

| 場景 | 推薦方法 | 關鍵要點 |
|:---|:---:|:---|
| 簡單單一幾何 | Code Block | 一個節點包含所有邏輯，成功率 100% |
| 複雜視覺化流程 | 原生節點 + 連線 | 需明確指定 `overload` 與 `preview` |
| 需要調試參數 | 原生節點 | 適合需要視覺化中間步驟的情境 |

---

### ✅ 鐵律與規範

#### 0. 先查節點 registry
- 建圖前先以 `get_node_recipe(names=[...])` 查詢所有節點；只有查不到的才用 `search_nodes`（使用其 `create` 欄位，fullName 無法建立節點）。
- 節點 id 用 GUID，執行成功後會自動記錄到 `domain/node_registry.json`。

#### 1. 幽靈連線排除 (Anti-Ghosting)
- **判定準則**：若 `analyze_workspace` 回報有節點，但畫面不可見，即為幽靈連線。
- **SOP**：`BIM Assistant` -> `Disconnect` -> 重新點擊 `Connect`。

#### 2. UI 執行緒 (Dispatcher) 規範
- 所有 C# 端對圖形的編修 **必須** 在 UI 執行緒執行。
- AI 應確保傳送的 JSON 格式符合 `nodes`/`connectors` 雙軌定義。

#### 3. 原生節點連線
- 必須使用 `fromPort` 與 `toPort` (取代舊有的 `fromIndex`)。
- 3D 節點建議明確標註 `"overload": "3D"`。

#### 4. Python Node 注入
- **名稱**: 必須為 `"Python Script"`。
- **欄位**: 必須包含 `"pythonCode"` (或 `"script"`)。
- **輸入數量**: 可選 `"inputCount"` (例如 `4`)。
- **引擎**: C# 自動設為 `"CPython3"`。
- **範例**: `{"id": "py01", "name": "Python Script", "pythonCode": "OUT = IN[0]", "inputCount": 2}`

---

## 🛠️ 故障排除

> **完整故障排除流程請參考**：[`domain/troubleshooting.md`](domain/troubleshooting.md)

| 症狀 | 可能原因 | 快速解決方案 |
|:---|:---|:---|
| Connection Refused | 背景 Server 未啟動 | 執行 `python bridge/python/server.py` |
| 成功但看不到節點 | 幽靈連線 | 重啟 Dynamo 並清除舊 Session |
| 指令無反應 | Dispatcher 阻塞 | 檢查 Dynamo 是否彈出對話框或忙碌 |

---

## 📁 參考文件
- **核心規範**: [GEMINI.md](file:///d:/AI/An/AutodeskDynamo_MCP/GEMINI.md)
- **實作計畫**: `implementation_plan.md`
- **啟動路徑**: `bridge/python/server.py`

## 🧪 自動化測試 (Autotest)
- **執行測試**: 在終端機執行 `.\autotest.ps1` (PowerShell) 或 `autotest` (CMD)。
- **AI 指令**: 對 AI 說「執行測試」或「Run autotest」，它將執行 `python tests/test_roadmap_features.py`。
- **測試內容**: 驗證節點搜索、Python 注入、外掛節點 (Clockwork) 與幾何運算。
