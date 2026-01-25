# Dynamo MCP 專案優化與未來規劃清單

本文件彙整了先前討論中產生的「更好的想法」以及尚未完全實作的優化規劃。

## 🚀 已達成核心突破 (現有基礎)

- **全類型節點放置**：透過 Deep Scan (CreationName) 機制，支援所有外掛 (Bimorph, Archi-lab) 與自定義節點。
- **Python 代碼注入**：三重保障機制 (Name Loop + 反射指令 + UI 強制同步)，徹底解決 Dynamo 3.3 代碼不顯示問題。
- **節點自動連線**：跨語言 ID 映射機制 (Python String ID ↔ C# GUID)，支援精確的 `fromPort`/`toPort` 連線。

---

## 🛠️ 待實作優化項目 (未完成的規劃)

### 1. 差異化重試與降級機制 (Differentiated Fallback) [DONE]
- **狀態**：✅ 已實作 (v1.2)
- **內容**：
    - Python 端支援 `_expand_native_nodes` (軌道 B)。
    - 失敗時自動觸發 `_generate_ds_code` 並降級至 `Number` (軌道 A) 重試。
- **成果**：大幅提升幾何創建成功率。

### 2. 埠位名稱動態比對 (Port Name Fallback) [DONE]
- **狀態**：✅ 已實作 (v1.2)
- **內容**：C# 端 `CreateConnection` 優先使用 `toPortName` 進行匹配。
- **成果**：解決跨版本埠位索引變動問題。

---

### 3. 多實例連線路由優化 (Multi-Session Routing) [DONE]
- **狀態**: ✅ 已實作 (v1.3)
- **內容**: 
    - `execute_dynamo_instructions` 支援 `sessionId` 參數。
    - 新增 `list_sessions` 工具。
- **成果**: 支援多個 Revit/Dynamo 視窗精確控制。

### 4. 效能監控儀表板 (Performance Dashboard) [DONE]
- **狀態**: ✅ 已實作 (v1.3)
- **內容**: 新增 `get_server_stats` 工具，回傳 Uptime、指令數與會話統計。
- **成果**: 通訊狀態透明化。

### 5. 心跳偵測與自動防幽靈 (Auto Anti-Ghosting) [DONE]
- **狀態**: ✅ 已實作 (v1.3)
- **內容**: 實作 `cleanup_stale_sessions` 邏輯，自動剔除超過 30 秒無響應的連線。
- **成果**: 零人工干預的環境維護。

### 6. Skill 封裝與權限自動化 [DONE]
- **狀態**: ✅ 已實作 (v1.3)
- **內容**: 建立 `setup.ps1`，使用 Directory Junction (Junction) 解決符號連結權限問題。
- **成果**: 大幅優化分發與安裝體驗。

---

## 📅 下一步建議

如果您確認以上清單正確，我們可以在新的對話框中選擇其中一個「高優先級」項目進行實作（例如：**差異化重試與降級機制**）。

---

**文件版本**: v1.1 (根據用戶意見修正降級策略)  
**整理日期**: 2026-01-25  
