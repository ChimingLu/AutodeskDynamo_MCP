---
description: 如何在 Dynamo 中成功放置並注入 Python Node
---

# 🐍 Python Node 放置與自動化 SOP

本 SOP 旨在指導 AI Agent 如何在 Dynamo 中成功創建 Python Script 節點並注入代碼，避免常見的 UI 不同步與引擎設置錯誤。

## 🎯 核心流程 (Workflow)

1.  **準備代碼**：確保 Python 代碼符合目標環境（如 Revit API）。
2.  **建構 JSON**：使用 `execute_dynamo_instructions` 工具，並在節點定義中包含 `pythonCode` 欄位。
3.  **座標計算**：確保節點不會與其他節點重疊。
4.  **發送指令**：執行 `execute_dynamo_instructions`。
5.  **驗證狀態**：使用 `analyze_workspace` 檢查節點是否成功創建。

## 📝 JSON 格式規範

在 `execute_dynamo_instructions` 的 `instructions` 字串中，Python 節點必須遵循以下結構：

```json
{
  "nodes": [
    {
      "id": "unique_py_id_01",
      "name": "Python Script",
      "pythonCode": "import clr\nclr.AddReference('RevitAPI')\n# Your code here...\nOUT = 'Success'",
      "inputCount": 2,
      "x": 500,
      "y": 300
    }
  ],
  "connectors": []
}
```

### 關鍵欄位說明：
- **`name`**: 必須為 `"Python Script"` (核心 C# 橋接器會自動嘗試多個名稱以確保相容性)。
- **`pythonCode`**: 必須包含完整的 Python 原始碼字串。
- **`inputCount`**: (新功能) 設置輸入埠數量。若未設置，預設通常為 1。
- **`engine` (選用)**: C# 端預設會設置為 `"CPython3"`。

## ⚠️ 應注意事項 (Precautions)

1.  **UI 執行緒與同步**：
    - C# 橋接器已實作「三層保障機制」（名稱循環、專用指令反射、UI 強制同步）。
    - 代理人**不需要**手動觸發 UI 更新，只需發送正確的 JSON 即可。
2.  **代碼轉義**：
    - 確保 Python 代碼中的換行符 (`\n`) 和引號在 JSON 字串中已正確轉義。
3.  **引用的庫**：
    - 若在 Revit 環境中，務必包含必要的 `clr.AddReference`。
4.  **座標重疊**：
    - 始終先執行 `analyze_workspace` 獲取當前畫布狀態，避免節點堆疊。

## 🛠️ 工具組合使用範例

### 步驟 1：分析環境
執行 `analyze_workspace` 獲取現有節點位置。

### 步驟 2：執行創建
```python
# 調用 execute_dynamo_instructions
instructions = {
    "nodes": [{
        "id": "get_rooms",
        "name": "Python Script",
        "pythonCode": "import clr\n# ... code ...\nOUT = rooms",
        "x": max_x + 200,
        "y": 300
    }]
}
```

## 🛡️ 故障排除

| 現象 | 可能原因 | 解決方法 |
| :--- | :--- | :--- |
| 節點創建了但代碼是空的 | `pythonCode` 欄位名稱拼錯 | 檢查 JSON 欄位是否為 `pythonCode` |
| 引擎噴錯 | 預設使用了 IronPython2 | C# 端應已自動設為 CPython3，若失敗請手動聯繫開發者 |
| 節點完全沒出現 | WebSocket 連線逾時 | 檢查 Dynamo 是否處於「運行中」狀態，暫停模式下可能無法即時顯示 |

---
**維護者**: Antigravity
**最後更新**: 2026-02-12
