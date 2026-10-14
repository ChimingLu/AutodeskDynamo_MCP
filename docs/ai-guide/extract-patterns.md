# 從既有 .dyn 批次擷取連接模式（去識別化）

適用情境：使用者陸續開啟很多舊的 `.dyn` 腳本，希望把其中有價值的節點鏈存進 `domain/node_registry.json`，並且不留下專案、路徑、人員或模型資訊。

與 `capture_node_pattern` 的差異：DynamoSandbox 沒有 Revit，Revit 節點會變成 Legacy Node（creationName 是 `"Legacy Node"`），直接擷取會存成建不出來的名稱。`tools/extract_patterns.py` 直接讀 `.dyn`，改用 FunctionSignature / UI 類別名稱當建立名稱，並自動去識別化。

## 例行步驟

1. **請使用者存檔**：在 Dynamo 按 Ctrl+S（節點值只能從已存檔的 `.dyn` 讀）。
2. **取得檔案路徑**：呼叫 MCP `get_graph_status`，取 `workspace.fileName`。
3. **列出候選鏈**：
   ```bash
   python tools/extract_patterns.py "<fileName>"
   ```
   依群組（Annotation）與連通子圖列出節點（id 前 8 碼、顯示名稱 → 建立名稱），並以 ⚠ 標出與既有模式「相同／包含於／包含」或相似度 ≥ 0.6 的組合（比對方式見下方「去重比對」）。也可以用 `get_node_pattern(query)` 再確認一次。
4. **挑出可重用的鏈，向使用者提案**：每個模式列出名稱、節點鏈、要去識別化的內容；**等使用者同意再寫入**。近似既有模式的，優先改成在既有模式補 gotchas。
5. **寫 spec JSON**（放在暫存資料夾，不進 repo）：
   ```json
   {
     "redact": ["業主名稱", "專案代號"],
     "patterns": [
       {
         "name": "模式名稱",
         "nodes": ["1c0b2a4f", "6726200e"],
         "description": "做什麼、何時用",
         "keywords": ["中文", "English"],
         "gotchas": ["需安裝的套件、範例值要改哪裡"],
         "overwrite": false
       }
     ]
   }
   ```
   `nodes` 填 id 前綴（候選清單的前 8 碼即可）。
6. **預覽 → 寫入**：
   ```bash
   python tools/extract_patterns.py "<fileName>" --spec spec.json
   python tools/extract_patterns.py "<fileName>" --spec spec.json --write
   ```
7. **全 registry 去重檢查**：`python tools/extract_patterns.py --check-registry`，列出相同／包含／相似的模式組合；有「包含於」時，通常把下游模式縮減成只剩新增的節點，並在 gotchas 寫明接上游哪個輸出。
8. **測試**：`python -m unittest tests/test_node_registry.py tests/test_extract_patterns.py`
9. **之後在 Dynamo for Revit 驗證**：空白工作區執行 `python tests/verify_node_registry_live.py`，通過的模式由 `captured` 變 `verified`。

## 自動去識別化的範圍

| 內容 | 處理 |
|---|---|
| Windows 路徑（`C:\...`、`\\server\...`） | → `C:/path/to/input` |
| GUID、Revit UniqueId（Code Block / String 值內） | → `<guid>` |
| 使用者名稱、`.dyn` 檔名、所在資料夾名稱、`OneDrive - 組織名稱` | → `<redacted>` |
| `--redact` 或 spec `redact` 指定的字串（業主、專案代號…） | → `<redacted>` |
| Select Model Elements 的 InstanceId | 不擷取 |
| 工作區節點 GUID、絕對座標 | 改成 ref 名稱與相對座標 |

外掛套件：寫入時會依 `.dyn` 的 NodeLibraryDependencies 自動記錄模式用到的套件（`packages: [{name, version, nodes}]`，version 為原腳本使用的版本）。`get_node_pattern` 會顯示「⚠ 需安裝外掛：…」，回傳的 instructions 也會帶 `groups`，`execute_dynamo_instructions` 放置後自動以此提醒標題框住整個模式（橘色群組）。

保留：自訂節點的 function GUID（套件定義，建立節點需要）、通用的參數名稱與品類名稱（當範例，在 gotchas 註明要依專案修改）。寫入前會再掃一次，仍含路徑或敏感字串的模式會被拒絕寫入。

自動規則抓不到業主名、案名縮寫等專有名詞，提案時請人工檢查節點值，必要時用 `--redact` 補上。

## 去重比對

每個模式轉成「節點＋連線」的多重集合再比較：

- 節點：建立名稱；Code Block 與 Python 另加上內容（空白壓縮，路徑、GUID、`C:/path/to/…`、`<redacted>`、`<guid>` 一律視為相同，所以去識別化前後的同一段鏈會判定為相同）。
- 連線：(來源節點, fromPort, 目標節點, toPort)。
- 關係：全部相同 →「相同」；一方完全包含在另一方 →「包含於／包含」；否則以 Jaccard 相似度（交集 ÷ 聯集）≥ 0.6 列為「相似」。

只有節點名稱相同、但 Code Block 內容或連線不同的模式（例如都只有 Code Block + List.Flatten）不會被列出。
