# 經驗教訓：Custom Node 建立策略 (GUID vs Name)

**日期**: 2026-02-13
**版本**: Dynamo 3.3+

## 🚨 問題描述 (The Problem)

在 Dynamo 3.3 (及可能的後續版本) 中，使用第三方套件 (Package) 的節點名稱 (Display Name 或 Full Name) 進行 `CreateNode` 操作時，經常發生建立失敗的情況。即使該節點在 Dynamo UI 中可搜尋且名稱完全一致 (e.g., `Clockwork.Core.Sequence.Passthrough` 或 `Passthrough`)。

**原因**:
Dynamo 內部的名稱解析機制變更，或者套件的路徑映射在 API 層級不穩定。對於 Custom Nodes，Dynamo 唯一穩定識別的是其內部的 **GUID**。

## 💡 解決方案 (The Solution)

**Rule: 對於 Custom Node (外掛節點)，始終優先使用 GUID 作為 `creationName`。**

### 操作流程

1.  **預檢 (Diagnosis)**:
    如果遇到外掛節點建立失敗（即使名稱看起來是對的），請先進行診斷。
    
2.  **特洛伊木馬分析 (Trojan Horse Analysis)**:
    - 要求使用者手動在 Canvas 上放置該目標節點。
    - 執行 `analyze_workspace` 工具。
    - 檢查回傳的 JSON，尋找該節點的 `creationName` 欄位（v3.3 起已增強此欄位顯示）。

    ```json
    {
      "name": "Passthrough",
      "fullName": "Dynamo.Graph.Nodes.CustomNodes.Function",
      "creationName": "ecce77dc-1290-438e-a056-970b256fd553",  <-- 這是關鍵!
      "x": 582.0,
      "y": 222.0
    }
    ```

3.  **使用 GUID 建立**:
    在 MCP 指令中，直接使用該 GUID 字串作為節點名稱：

    ```json
    {
        "id": "node_1",
        "name": "ecce77dc-1290-438e-a056-970b256fd553",  // 使用 GUID
        "x": 100,
        "y": 100
    }
    ```

## 📚 案例記錄

| 套件 | 節點名稱 (Display) | 節點 GUID | 備註 |
|:---|:---|:---|:---|
| Clockwork | Passthrough | `ecce77dc-1290-438e-a056-970b256fd553` | 數據流直通節點 |
| (待補) | | | |

## ✅ 結論

不要依賴字串名稱來猜測 Custom Nodes 的身分。**Trust the GUID.**
