# Dynamo MCP 快速參考手冊 (Quick Reference)

## 📌 核心連線資訊
- **MCP Server**: `http://127.0.0.1:5050/mcp/`
- **節點庫名稱**: `DynamoMCPListener.MCPControls`
- **關鍵節點**:
    - `StartMCPServer`: 啟動 HTTP 監聽器（Port 5050）
    - `StopMCPServer`: 手動停止監聽器（用於故障排除）

---

## 🛠️ 故障排除 SOP

### 1. 無法連線 (Connection Refused)
- **檢查**: Dynamo 視窗是否開啟？
- **檢查**: 是否已放置 `StartMCPServer` 節點且顯示為 `Active`？
- **修復**: 重新放置 `StartMCPServer` 節點。

### 2. 幽靈連線 (Ghost Listener)
**症狀**：AI 顯示 OK，但 Dynamo 畫面無反應。
**場景**：在 Revit 中重開了 Dynamo 視窗。
**修復 SOP**：
1. **清理**: 放置 `StopMCPServer` 節點，確認顯示 "successfully stopped"。
2. **移除**: **必須刪除** Stop 節點。
3. **重建**: 放置 `StartMCPServer` 節點。
4. **驗證**: 執行 `analyze_workspace` 確認節點數恢復為 1。

---

## 🧠 重大教訓紀錄

### 2026-01-05: 視窗重啟偵測與強制奪取

**問題**：
舊版監聽器使用靜態 SessionID 且不會隨視窗關閉而停止，導致連線錯位。

**技術修復 (v2.3)**：
- **強制奪取 (Force Takeover)**：新實例會主動殺死舊實例。
- **生命週期 Hook**：監聽 `Window.Closed` 事件。
- **實體 Session**：SessionID 跟隨伺服器實體，而非類別。

**鐵律**：
- **檢查第一**：執行任何指令前必先 `analyze_workspace`。
- **質疑狀態**：當節點數異常（例如預期是空但看到舊節點）時，主動發起重連。

---

## 📁 參考文件
- **完整規範**: [MCP_GUIDELINES.md](file:///d:/AI/An/AutodeskDynamo_MCP/MCP_GUIDELINES.md)
- **節點庫清單**: `DynamoViewExtension/common_nodes.json`
- **實作細節**: `DynamoViewExtension/src/SimpleHttpServer.cs` (強制奪取邏輯)
