---
name: dynamo-script-analysis
description: 專門分析當前 Dynamo 腳本邏輯，將工作區結構收斂成 Mermaid 流程圖、邏輯摘要與技術文件。當使用者要求「分析目前 Dynamo 腳本邏輯」、「產生流程圖」、「輸出 /image 類型分析」、「把 graph 解釋成可讀流程」時使用。
---

# Dynamo Script Analysis Skill

將「讀取當前工作區並轉成可讀邏輯圖」流程標準化，避免每次都用臨時 Prompt 手工猜測節點意義。

## 何時使用

符合任一條件就啟用本 Skill：

1. 使用者要求分析目前 Dynamo 腳本邏輯。
2. 使用者想要 Mermaid 流程圖或 `/image` 類型技術摘要。
3. 需要把大型 Dynamo graph 壓縮成可討論的輸入 / 運算 / 輸出流程。
4. 需要離線驗證分析邏輯，不依賴現場 Dynamo 連線。

## 核心原則

1. 先取結構，再寫解讀。
2. 大型圖表要摘要，不要把所有節點硬塞進圖。
3. 流程圖是為了說明資料流，不是重建整張 Dynamo 畫布。
4. 優先產出輸入 / 核心運算 / 輸出三段式視圖。

## 標準步驟

### Step 0: 先確認 Mermaid 方向與模式

**方向（direction）** 由使用者決定，僅接受以下值：

1. `TD`：上到下（預設）
2. `LR`：左到右
3. `RL`：右到左
4. `BT`：下到上

若使用者未指定，預設使用 `TD`。

**模式（mode）** 決定圖表的資訊密度：

| mode | 說明 | 適用場景 |
|------|------|----------|
| `pipeline`（預設） | 工作流階段觀，自動分層並加中文描述 | 給人看的可讀邏輯圖 |
| `semantic` | 同名節點合併並標注數量（如 Arc ×3） | 中型分析，需顯示節點比例 |
| `detail` | 每個 Dynamo 節點對應一格（1:1） | debug、追查特定節點 |

若使用者未指定，預設使用 `pipeline`。

### Step 1: 取得工作區資料

優先使用正式工具（預設 TD + pipeline，最可讀）：

```json
{
  "name": "generate_workspace_mermaid",
  "arguments": {
    "direction": "<USER_CHOICE_OR_TD>",
    "mode": "<pipeline|semantic|detail>",
    "maxNodes": 60
  }
}
```

若沒有即時連線，可改用 snapshot：

```json
{
  "name": "generate_workspace_mermaid",
  "arguments": {
    "snapshotPath": "tests/fixtures/workspace_mermaid_sample.json",
    "direction": "<USER_CHOICE_OR_TD>",
    "mode": "pipeline",
    "maxNodes": 20
  }
}
```

### Step 2: 解讀輸出

至少使用以下欄位：

1. `summary`: 檔名、節點數、複雜度、是否摘要截斷。
2. `logic_steps`: 三到數步的人類可讀邏輯摘要。
3. `mermaid`: 可直接嵌入 Markdown 的流程圖。
4. `top_node_types`: 判斷主要運算類型。

### Step 3: 視需求輸出文件

若需要保留分析報告，啟用 `saveToFile=true`：

```json
{
  "name": "generate_workspace_mermaid",
  "arguments": {
    "saveToFile": true,
    "direction": "<USER_CHOICE_OR_TD>",
    "mode": "pipeline",
    "maxNodes": 60
  }
}
```

### Step 4: 驗證 Mermaid 並輸出圖片（可選）

若要避免「圖能產生但無法渲染」的狀況，先驗證再發佈。

前置需求：

1. 安裝 mermaid-cli：`npm install -g @mermaid-js/mermaid-cli`

建議命令（預設 TD + pipeline）：

```bash
python tools/generate_mermaid_artifacts.py --save --output image/current_workspace_logic.md --validate
```

若要同時輸出 PNG：

```bash
python tools/generate_mermaid_artifacts.py --save --output image/current_workspace_logic.md --validate --render png
```

指定方向或模式：

```bash
python tools/generate_mermaid_artifacts.py --direction LR --mode semantic --save --output image/current_workspace_logic.md
```

### Step 5: 清理測試與中間產物（建議）

若本次是驗證流程而非正式交付，完成後刪除中間輸出，避免污染版本控制。

建議清理清單：

1. `tests/temp/*.json`
2. 臨時命名的 `image/*_TD.md`、`image/*_simplified.md`
3. 驗證階段產生但不需保留的 `.mmd`、`.png`、`.svg`

Windows PowerShell 範例：

```powershell
if (Test-Path tests/temp) { Remove-Item tests/temp/*.json -Force -ErrorAction SilentlyContinue }
if (Test-Path image) { Remove-Item image/*_TD.md,image/*_simplified.md,image/*.mmd -Force -ErrorAction SilentlyContinue }
```

方向與模式範例（使用者要求由上而下）：

```json
{
  "name": "generate_workspace_mermaid",
  "arguments": {
    "direction": "TD",
    "mode": "pipeline",
    "maxNodes": 60,
    "saveToFile": true
  }
}
```

## 推薦回覆格式

1. 先說腳本目的與整體資料流。
2. 再列 3-5 個邏輯步驟。
3. 最後附 Mermaid 流程圖或報告路徑。
4. 若已驗證，補一句「已通過 Mermaid 渲染驗證」。
5. 若為測試回合，補一句「已清理中間產物」。

## 相關檔案

1. `bridge/python/server.py`
2. `domain/visual_analysis_workflow.md`
3. `domain/commands/image.md`
4. `tests/verify_generate_workspace_mermaid.py`
5. `tools/generate_mermaid_artifacts.py`

---

Skill 版本：1.4
最後更新：2026-06-21