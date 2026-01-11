---
description: Dynamo MCP 標準啟動檢查流程
trigger: 每次 AI 對話開始或環境變動
version: 1.0
last_updated: 2026-01-11
---

# Dynamo MCP 啟動檢查清單

> **目的**：確保 AI 在執行任何實質操作前，完整掌握 Dynamo 當前狀態，避免幽靈連線、Session 錯位等問題。

---

## 📋 強制執行順序

### 1️⃣ 環境連線檢查

**執行動作**：
```python
analyze_workspace()
```

**必要驗證**：
- [ ] 回應包含 `sessionId` 欄位
- [ ] 回應包含 `nodeCount` 欄位
- [ ] 回應包含 `workspaceName` 欄位
- [ ] HTTP 狀態碼為 200

**若失敗** → 導向 [`troubleshooting.md#連線失敗`](troubleshooting.md#連線失敗)

---

### 2️⃣ SessionID 變動感知

**目的**：偵測 Dynamo 是否已重新啟動（新實例）

**檢查邏輯**：
```
IF 當前 sessionId ≠ 前次記錄的 sessionId
THEN 
  - 判定為新 Dynamo 實例
  - 清空內部 _nodeIdMap 快取（避免使用舊 GUID）
  - 向使用者主動回報：「🔄 偵測到 Dynamo 新會話」
```

**AI 行為準則**：
- 第一次執行時，記錄 `sessionId` 作為基準
- 後續每次 `analyze_workspace` 都進行對比
- 若偵測變動，**必須**在回覆中明確告知使用者

---

### 3️⃣ 幽靈連線偵測

**定義**：  
Revit 未關閉但 Dynamo 視窗被重新開啟，導致 AI 指令成功但使用者看不到結果。

**判定準則**：
```
IF analyze_workspace.nodeCount > 1 
   AND 使用者表示「剛開新檔案」或「看不到節點」
THEN 判定為幽靈連線
```

**修復流程** → 導向 [`troubleshooting.md#幽靈連線`](troubleshooting.md#幽靈連線)

**預防措施**：
- 每次對話開始時強制執行本檢查清單
- 若 `nodeCount` 與使用者描述不符，主動質疑並確認

---

### 4️⃣ 強制回報

執行完畢後，AI **必須**向使用者回報以下資訊：

```markdown
✅ **環境檢查完成**
- **Workspace**: [workspaceName]
- **Node Count**: [nodeCount]
- **Session**: [是否延續 / 新實例]
- **StartMCPServer**: [已放置 / 建議放置]
```

**格式要求**：
- 使用 Emoji 與粗體提升可讀性
- 若偵測到異常（如缺少 StartMCPServer），主動提示

---

## 🔗 相關工具與文件

### MCP 工具
- **`analyze_workspace`**：執行狀態檢查的核心工具
  - 實作位置：`server.py::analyze_workspace()`
  - 內部調用：`_check_dynamo_connection()` → `_detect_potential_restart()`

### 參考文件
- **故障排除**：[`domain/troubleshooting.md`](troubleshooting.md)
- **快速參考**：[`QUICK_REFERENCE.md`](../QUICK_REFERENCE.md)
- **核心規範**：[`GEMINI.md`](../GEMINI.md)

---

## ⚠️ 常見錯誤與解決

| 錯誤現象 | 可能原因 | 解決方案 |
|:---|:---|:---|
| `Connection Refused` | Dynamo 未啟動或未放置 StartMCPServer 節點 | [troubleshooting.md#連線失敗](troubleshooting.md#連線失敗) |
| `nodeCount` 異常大 | 幽靈連線（舊 Session 殘留） | [troubleshooting.md#幽靈連線](troubleshooting.md#幽靈連線) |
| `sessionId` 突然變動 | Dynamo 已重新啟動 | 清空快取並重新初始化 |
| 回應包含 `mcp_warning` | 缺少 StartMCPServer 節點 | 提示使用者放置該節點 |

---

## 📌 AI 行為檢查點

執行本檢查清單前，AI 必須確認：

- [ ] 這是對話的**第一輪互動**？ → 必須執行完整檢查
- [ ] 使用者提及「重新開啟 Dynamo」？ → 必須執行 SessionID 檢查
- [ ] 即將執行 `execute_dynamo_instructions`？ → 必須先執行環境檢查
- [ ] 使用者回報「看不到節點」？ → 必須執行幽靈連線偵測

**鐵律**：寧可過度檢查，也不可遺漏檢查。
