# 🛠️ MCP Tools: AI Agent 控制指南 (Dynamo Edition)

本文件定義為 AI Agent (MCP Client) 專用的技術工具手冊，匯集了控制 Dynamo 節點的核心技術、最佳實踐與 API 調用規範。

---

## 🐍 Python Node 自動化 (核心工具)

### 1. 節點建立與代碼注入 (Injection Mechanism)
Agent 應使用 `execute_dynamo_instructions` 並在 `instructions` 中包含以下屬性：

| 屬性 | 說明 | 範例 |
|:---|:---|:---|
| `name` | 必須設為 `"Python Script"` | `"name": "Python Script"` |
| `pythonCode` | 主要代碼存放欄位 (相容 `script`) | `"pythonCode": "OUT = IN[0]"` |
| `inputCount` | **(新功能)** 指定輸入埠數量 | `"inputCount": 3` |

### 2. 埠位調整技術 (Port Count Engineering)
現在支援動態調整埠位數量，Agent 不需要手動執行多個指令，只需在 `nodes` 定義中加入 `inputCount` 即可。

**解決問題**：防止 `IndexError: list index out of range`。

**內部原理**：C# 橋接器會偵測此欄位，並透過反射動態調用 `AddInput()` 或 `RemoveInput()`。

---

## 🧩 幾何節點策略 (Geometry Strategy)

### 軌道 A：Code Block 模式 (快速、穩定)
對於簡單的 `Point.ByCoordinates` 等操作，優先使用 Code Block 將邏輯封裝在單一節點中。

### 軌道 B：原生節點模式 (視覺化、可調參數)
當需要使用者手動調整參數（如 Slider）時，使用原生節點配合 `connectors`。

---

## 🛡️ 鐵律 (Iron Laws)

1. **環境預檢**：任何修改前必須執行 `analyze_workspace`。
2. **座標防撞**：新節點 X 座標應至少與現有節點間隔 300 單位。
3. **Session 路由**：在多個 Revit 實例開啟時，務必指定 `sessionId` 以防指令錯位。
4. **Python 保留字**：在庫引用時，優先使用 `import clr` 並正確轉義 `\n`。

---

## 📈 常用指令組合 (Power Combos)

### 建立「資料讀取 -> 分析 -> 輸出」工作流：
1. `search_nodes` 尋找必要的 Revit 收集器。
2. 建立一個具有多個輸入 (`inputCount`) 的 `Python Script` 節點。
3. 建立 `Connectors` 將收集器輸出連至 Python 輸入。

---
**最後更新**: 2026-02-12
**維護者**: Antigravity
**版本**: v1.0
