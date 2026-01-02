為了確保 AI 在控制 Autodesk Dynamo 時不發生低級錯誤（如點座標重疊、誤用 2D 節點等），特訂定此規範。**AI 在執行任何繪圖指令前必須檢查此規範。**

## 0. 啟動與狀態檢查 (Startup & Status Check)
- **強制執行分析**：AI 在進行任何實質作業（放置節點、連線、載入腳本）前，**必須**先執行 `analyze_workspace` 工具。
- **重啟感知與通報**：
    - 若發現 `nodeCount` 較前次對話顯著減少（如歸零），AI **必須**詢問使用者是否重啟了 Dynamo。
    - 每次對話開始或環境變動後，**必須**主動回報：
        - `Workspace Name`: 當前檔案名稱。
        - `Node Count`: 當前節點數。
        - `Connection`: 確認連線是否暢通（透過 ViewExtension 自動啟動或節點手動啟動）。
- **監聽狀態提醒**：若 `analyze_workspace` 成功回傳，AI 將其視為所有操作的前置檢查。

## 1. 節點選用準則 (Node Selection)
- **拒絕歧義**：嚴禁使用點選單簡稱（如 `Point.ByCoordinates`）。必須優先參考 `common_nodes.json` 內的 `fullName`。
- **Overload 處理規則**：
    - 若發現某個節點具備多個重載（Overload）版本（如 `Point.ByCoordinates` 有 2D 與 3D 版本），且 AI 無法根據上下文百分之百確定時，**禁止**盲目嘗試。
    - 此時 **必須** 列出所有可用的 Overload 選項，並請求使用者選擇正確的版本後再繼續執行。
- **強制 3D 識別**：若發現 `Point.ByCoordinates` 被誤判為 2D (僅 XY)，AI **必須**改用 `Code Block` 寫入 `Point.ByCoordinates(x, y, z);` 以從根本上保證 3D 埠位。
- **全路徑引用**：發送指令時，節點名稱應盡量包含完整命名空間。

## 2. 數值輸入準則 (Input Standards)
- **禁止預設值**：嚴禁建立「懸空」的幾何節點。所有幾何節點的座標輸入（X, Y, Z）必須連接外部輸入節點。
- **Code Block 強制化**：
    - 所有數值（Number）必須透過 `Code Block` (指令中稱為 `Number`) 節點產生。
    - 數值內容必須以分號結尾（例如 `10;`）。
- **可讀性佈局**：輸入節點應位於幾何節點的左側，並保持適當的 Y 軸間距（建議間隔 100 單位），避免節點在畫面上重疊。

## 3. 連線與驗證準則 (Connection & Verification)
- **三埠必連**：對於 3D 點，`x`, `y`, `z` 三個 Port (0, 1, 2) 必須全部建立連線。
- **埠位索引檢查**：在發送指令前，必須對照 `common_nodes.json` 確認每個 Port 的 Index 是否正確。
- **自我審查循環**：
    1. 生成 JSON 指令。
    2. 檢查：XYZ 是否都有對應的 Code Block？
    3. 檢查：連線是否指向了正確的埠位索引？
    4. 執行並使用 `analyze_workspace` 檢查是否有警告。

## 4. 故障排除規則
- 若 `analyze_workspace` 回傳 `Warning` 或點重疊，AI 必須立即分析是否有 Port 未正確給值，並禁止在未修正邏輯的情況下重複發送相同指令。
