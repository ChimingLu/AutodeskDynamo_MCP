為了確保 AI 在控制 Autodesk Dynamo 時不發生低級錯誤（如點座標重疊、誤用 2D 節點等），特訂定此規範。**AI 在執行任何繪圖指令前必須檢查此規範。**

## 0. 啟動與狀態檢查 (Startup & Status Check)
- **強制執行分析**：AI 在進行任何實質作業（放置節點、連線、載入腳本）前，**必須**先執行 `analyze_workspace` 工具。
- **幽靈連線 (Ghost Listener) 偵測法**：
    - **定義**：Revit 未關閉但重開了 Dynamo 視窗。
    - **特徵**：AI 執行指令回報成功，但使用者回報「沒看到東西」或「工作區是空的」。
    - **判定準則**：若 `analyze_workspace` 回傳的 `nodeCount > 1`（除了連線節點），但使用者表示是新開的空白檔案，**判定為幽靈連線**。
    - **處理邏輯**：AI 必須強制停止當前操作，引導使用者執行：`StopMCPServer` -> 刪除 Stop 節點 -> `StartMCPServer`。
- **SessionId 變動感知**：
    - 若 `sessionId` 與前次記錄不符，表示 Dynamo 伺服器已重新實例化。
    - AI 必須重置內部 `_nodeIdMap` 快取，避免使用舊的節點 GUID。
- **強制回報**：每次對話開始或環境變動後，**必須**主動回報：
    - `Workspace Name`: 當前檔案名稱。
    - `Node Count`: 當前節點數。
    - `Session State`: 確認 Session ID 是否延續或為新實例。

## 1. 節點創建的正確方法 (Critical: Node Creation Method)

### ✅ **唯一正確的做法：使用單一 Code Block 節點**
```json
{
    "nodes": [
        {
            "id": "my_geometry",
            "name": "Number",
            "x": 400,
            "y": 400,
            "value": "Line.ByStartPointEndPoint(Point.ByCoordinates(0, 0, 0), Point.ByCoordinates(100, 100, 100));"
        }
    ],
    "connectors": []
}
```

**關鍵要點**：
1. **節點名稱必須是 `"Number"`**（不是 "Code Block"）
2. **在 `value` 欄位寫完整的 DesignScript 代碼**
3. **代碼必須以分號 `;` 結尾**
4. **可以在一個 Code Block 中創建整個幾何圖形**
5. GraphHandler.cs 會自動將 `"Number"` 轉換為 Code Block 節點

### ❌ **絕對禁止的錯誤做法**
```json
// ❌ 錯誤 1: 試圖直接創建 Point.ByCoordinates 節點
{
    "nodes": [
        {"id": "pt1", "name": "Point.ByCoordinates", "x": 100, "y": 100}
    ]
}

// ❌ 錯誤 2: 試圖創建多個分離的 Number 節點並連接
{
    "nodes": [
        {"id": "x1", "name": "Number", "value": 5, "x": 100, "y": 100},
        {"id": "pt1", "name": "Point.ByCoordinates", "x": 300, "y": 150}
    ],
    "connectors": [{"from": "x1", "to": "pt1", "fromPort": 0, "toPort": 0}]
}

// ❌ 錯誤 3: 使用 "Code Block" 作為名稱
{
    "nodes": [
        {"id": "cb", "name": "Code Block", "code": "...", "x": 100, "y": 100}
    ]
}
```

**為何這些方法會失敗**：
- Dynamo API 的 `CreateNodeCommand` 無法直接創建帶參數的 `Point.ByCoordinates` 節點
- `Code Block` 作為節點名稱會導致創建失敗
- 分離的節點創建會因為 API 限制而失敗

### 📋 **實戰範例**

**創建一條線**：
```json
{
    "nodes": [{
        "id": "line1",
        "name": "Number",
        "value": "Line.ByStartPointEndPoint(Point.ByCoordinates(0,0,0), Point.ByCoordinates(100,100,100));",
        "x": 300, "y": 300
    }],
    "connectors": []
}
```

**創建一個立方體**：
```json
{
    "nodes": [{
        "id": "cuboid1",
        "name": "Number",
        "value": "Cuboid.ByLengths(Point.ByCoordinates(0,0,0), 10, 10, 10);",
        "x": 300, "y": 300
    }],
    "connectors": []
}
```

**創建複雜幾何（多個 Code Block）**：
```json
{
    "nodes": [
        {
            "id": "sphere",
            "name": "Number",
            "value": "Sphere.ByCenterPointRadius(Point.ByCoordinates(0,0,0), 5);",
            "x": 200, "y": 200
        },
        {
            "id": "box",
            "name": "Number",
            "value": "Cuboid.ByLengths(Point.ByCoordinates(20,0,0), 8, 8, 8);",
            "x": 200, "y": 400
        }
    ],
    "connectors": []
}
```

## 2. 節點選用準則 (Node Selection)
- **拒絕歧義**：嚴禁使用點選單簡稱（如 `Point.ByCoordinates`）。必須優先參考 `common_nodes.json` 內的 `fullName`。
- **Overload 處理規則**：
    - 若發現某個節點具備多個重載（Overload）版本（如 `Point.ByCoordinates` 有 2D 與 3D 版本），且 AI 無法根據上下文百分之百確定時，**禁止**盲目嘗試。
    - 此時 **必須** 列出所有可用的 Overload 選項，並請求使用者選擇正確的版本後再繼續執行。
- **強制 3D 識別**：若發現 `Point.ByCoordinates` 被誤判為 2D (僅 XY)，AI **必須**改用 `Code Block` 寫入 `Point.ByCoordinates(x, y, z);` 以從根本上保證 3D 埠位。
- **全路徑引用**：發送指令時，節點名稱應盡量包含完整命名空間。

## 3. 數值輸入準則 (Input Standards)
- **禁止預設值**：嚴禁建立「懸空」的幾何節點。所有幾何節點的座標輸入（X, Y, Z）必須連接外部輸入節點。
- **Code Block 強制化**：
    - 所有數值（Number）必須透過 `Code Block` (指令中稱為 `Number`) 節點產生。
    - 數值內容必須以分號結尾（例如 `10;`）。
- **可讀性佈局**：輸入節點應位於幾何節點的左側，並保持適當的 Y 軸間距（建議間隔 100 單位），避免節點在畫面上重疊。

## 4. 連線與驗證準則 (Connection & Verification)
- **三埠必連**：對於 3D 點，`x`, `y`, `z` 三個 Port (0, 1, 2) 必須全部建立連線。
- **埠位索引檢查**：在發送指令前，必須對照 `common_nodes.json` 確認每個 Port 的 Index 是否正確。
- **自我審查循環**：
    1. 生成 JSON 指令。
    2. 檢查：XYZ 是否都有對應的 Code Block？
    3. 檢查：連線是否指向了正確的埠位索引？
    4. 執行並使用 `analyze_workspace` 檢查是否有警告。

## 5. 故障排除規則
- 若 `analyze_workspace` 回傳 `Warning` 或點重疊，AI 必須立即分析是否有 Port 未正確給值，並禁止在未修正邏輯的情況下重複發送相同指令。

## 6. 腳本庫管理 (Script Library Management) 
- **功能描述**：新版 MCP 支援將成功的 Dynamo 指令快照保存為腳本 (`DynamoScripts/*.json`)，以便重複使用。
- **最佳實踐**：
    1. **驗證後保存**：只有在 AI 確認執行成功 (無錯誤、無幽靈連線、使用者滿意) 後，才主動詢問使用者是否保存為腳本。
    2. **模組化命名**：腳本名稱應具備描述性 (如 `grid_10x10`, `basic_cube_param`)，不包含副檔名。
    3. **復用優先**：當使用者請求繪製標準圖形時，先使用 `get_script_library` 查詢是否有現成腳本，若有則優先使用 `load_script_from_library`，這比重新生成指令更穩定。
    4. **參數化載入**：`load_script_from_library` 支援 `base_x` 與 `base_y` 偏移量，載入時應計算適當位置避免與現有圖形重疊。
- **操作流程範例**：
    ```python
    # 1. 查詢庫存
    scripts = mcp.get_script_library()
    
    # 2. 若存在，載入並執行 (偏移 500 單位以免重疊)
    json_content = mcp.load_script_from_library("basic_house", base_x=500, base_y=0)
    mcp.execute_dynamo_instructions(json_content)
    ```
