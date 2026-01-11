# Dynamo MCP 快速參考手冊 (Quick Reference)

## 📌 核心連線資訊
- **MCP Server**: `http://127.0.0.1:5050/mcp/`
- **節點庫名稱**: `DynamoMCPListener.MCPControls`
- **關鍵節點**:
    - `StartMCPServer`: 啟動 HTTP 監聽器（Port 5050）
    - `StopMCPServer`: 手動停止監聽器（用於故障排除）

---

## 🛠️ 故障排除

> **完整故障排除流程請參考**：[`domain/troubleshooting.md`](domain/troubleshooting.md)

### 快速診斷

| 症狀 | 可能原因 | 快速解決方案 |
|:---|:---|:---|
| Connection Refused | 未啟動監聽器 | 放置 `StartMCPServer` 節點 |
| AI 顯示成功但看不到節點 | 幽靈連線 | 執行 Stop → 刪除 → Start 流程 |
| 多個程序警告 | 殭屍程序 | 強制終止所有 Dynamo/Revit |

**詳細 SOP**：
- 🔴 [連線失敗](domain/troubleshooting.md#連線失敗)
- 👻 [幽靈連線](domain/troubleshooting.md#幽靈連線)
- ⚠️ [多程序衝突](domain/troubleshooting.md#多程序衝突)
- 🔧 [節點創建失敗](domain/troubleshooting.md#節點創建失敗)

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
- **完整規範**: [GEMINI.md](file:///d:/AI/An/AutodeskDynamo_MCP/GEMINI.md)
- **節點庫清單**: `DynamoViewExtension/common_nodes.json`
- **實作細節**: `DynamoViewExtension/src/SimpleHttpServer.cs` (強制奪取邏輯)
