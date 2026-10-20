---
name: "dynamo-connection-patterns"
description: "在 Dynamo 透過 dynamo-mcp 建圖、存下好用的節點連接模式、或從 .dyn 擷取並去識別化模式時使用。"
---

# Dynamo 節點連接模式

連接模式 = 一段可重用的節點鏈（節點 + 連線 + 值 + 注意事項），存在 repo `ChimingLu/AutodeskDynamo_MCP` 的 `domain/node_registry.json` 的 `patterns`。這是所有 agent 共用的唯一來源：**不要把模式內容複製到別處**，一律用 MCP 工具讀寫。

回覆使用者用繁體中文。

## 1. 建圖前：先查模式

1. `get_node_pattern(query="需求描述")`：中英文關鍵字都可。命中就直接拿回可執行的 instructions JSON（每次產生新 GUID，可用 `baseX/baseY` 指定位置），交給 `execute_dynamo_instructions`。
2. `get_node_pattern()` 不帶參數 = 列出全部模式與一行說明。
3. 模式外的節點用 `get_node_recipe(names=[...])` 取建立名稱與埠順序；兩者都沒有才用 `search_nodes`。
4. 回傳若有「⚠ 需安裝外掛：…」，先告訴使用者要裝哪個套件（Clockwork、archi-lab、DynaMEP、Genius Loci…）。
5. 讀 gotchas：範例參數名稱（如「門高」「牆面塗層」）、品類、需手動選的下拉值（Select Phase、Convert By Units）、要接的上游模式，都要依使用者專案調整並說明。
6. 狀態 `captured` = 還沒在 Revit 實機驗證過，建好後請使用者執行確認。

## 2. 什麼值得存成模式

值得：2 個以上節點、解決一個具體子問題、換掉幾個值就能用在別的專案（例：品類→元件→取參數、房間邊界→內縮建牆、BoundingBox 干涉篩選、Python 呼叫 Revit API 的小段）。

不值得：單一普通節點、純示範（隨機線、Hello World）、只對一個專案有意義的寫死流程、跟既有模式幾乎相同（改成在既有模式補 gotchas）。

## 3. 存模式：依來源選一種方式

| 來源 | 做法 |
|---|---|
| Claude 剛用 MCP 建好並執行成功 | `save_node_pattern(name, instructions=<剛執行的同一份 JSON>, description, keywords, gotchas)`；Dynamo 連線時會對照工作區，節點與連線都在才標 verified |
| 使用者在 Dynamo 手動拉好 | 請使用者 Ctrl+S 存檔、框選節點，再 `capture_node_pattern(name, description, keywords, gotchas)`；存成 captured |
| 既有 .dyn（尤其在 DynamoSandbox 開 Revit 腳本，Revit 節點顯示為 Legacy Node） | 用 `tools/extract_patterns.py`，步驟見 `docs/ai-guide/extract-patterns.md` |

命名：中文、描述「輸入→處理→輸出」，例「房間邊界→依牆類型厚度內縮建立裝修牆」。keywords 中英並列。gotchas 寫：需要的套件、範例值要改哪裡、要接哪個上游模式、需手動選的選項。

## 4. 從 .dyn 擷取（重複性最高的流程）

1. 請使用者在 Dynamo 按 Ctrl+S（節點值只能從存檔讀）。
2. `get_graph_status` 取 `workspace.fileName`。工作區只在使用者電腦上，需要時在那台電腦上執行。
3. `python tools/extract_patterns.py "<fileName>"` 列出候選鏈；⚠ 標記的是與既有模式相同／包含／相似的組合。
4. **先向使用者提案，等同意才寫入**：每組列名稱、節點鏈（一行）、需要的套件、去識別化了什麼。近似既有模式的，提議補 gotchas 而不是新增。結尾給一個好回答的問題（例：回「全部存」或指定編號）。
5. 寫 spec JSON 到暫存資料夾（不進 repo）：`{"redact": [...], "patterns": [{"name", "nodes": [id 前 8 碼], "description", "keywords", "gotchas"}]}`。
6. 預覽 `--spec spec.json`，確認後加 `--write`。
7. `python tools/extract_patterns.py --check-registry` 做全 registry 去重。
8. `python -m unittest tests/test_node_registry.py tests/test_extract_patterns.py`（`tests/` 被 .gitignore 排除，新測試檔要 `git add -f`）。

## 5. 去識別化（每次寫入前都要做）

工具會自動處理，但寫入後仍要搜尋整個 registry 確認 0 筆：

- Windows 路徑、網路路徑 → `C:/path/to/input`（輸出用 `C:/path/to/output`、Excel 用 `C:/path/to/input.xlsx`）
- 使用者帳號（`C:\Users\<name>`）、OneDrive 組織名、公司名、業主名、案名、.dyn 檔名與資料夾名 → 不存或 `<redacted>`
- Revit 元素 ID / UniqueId、Select Model Elements 的選取 → 不存，在 gotchas 註明「執行時重新選取」
- 工作區節點 GUID、絕對座標 → 工具會換成 ref 名稱與相對座標
- 自動規則抓不到專有名詞縮寫：提案前人工看過 Code Block、String、Python 內容，必要時 `--redact` 補上

保留：套件自訂節點的 function GUID（建立節點需要）、通用參數名稱與品類名稱（當範例，gotchas 註明依專案修改）。

## 6. 收尾

- 告訴使用者這次新增幾組、registry 共幾組、哪些還是 captured。
- 驗證：在 Dynamo for Revit 開空白工作區（Manual 執行模式）跑 `python tests/verify_node_registry_live.py`，通過的會自動改為 verified。
- registry 的修改要 commit 並開 PR 才會同步給其他電腦與 agent；沒被要求就先問再推。

## 規則

- 節點 id 一律用 GUID。
- 不在 Python 節點內刪節點或修改工作區（會讓 Dynamo 當掉）。
- Code Block 內呼叫 List.* 要寫 `DSCore.List.*`。
- 完整規則：`get_mcp_guidelines`（即 GEMINI.md）。