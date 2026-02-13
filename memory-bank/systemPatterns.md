# 系統架構與設計模式 (System Patterns)

> **這份文件描述系統架構、技術決策與關鍵設計模式。它是單一真理來源 (SSOT)。**

## 🏗️ 系統架構 (System Architecture)

### 1. **Core Bridge (MCP Server)**
- **Role**: 轉換 MCP Request -> WebSocket Message。
- **Component**: `server.py` (Python)。
- **Patterns**:
  - **Single WebSocket**: 使用單一 socket 處理多 Session。
  - **AsyncIO**: 確保高效併發。
  - **Memory Bank Integration**: 每次啟動讀取 Memory Bank。

### 2. **Frontend Extension (Dynamo ViewExtension)**
- **Role**: 接收 WebSocket 指令，操作 Dynamo API。
- **Component**: `DynamoMCPListener` (C#)。
- **Core Pattern**: **Upsert Logic** using `GraphHandler.cs`.
  - **Check Existence**: 使用 GUID 檢查節點是否存在。
  - **Update**: 僅更新屬性 (Position, Value, Code)。
  - **Insert**: 若不存在，則創建新節點。

### 3. **Communication Protocol**
- **JSON-RPC 2.0 (MCP)**: 標準化指令格式。
- **Custom WebSocket JSON**: 自定義 Dynamo 指令格式 (`nodes`, `connectors`)。

## 📐 關鍵技術決策 (Design Decisions)

| 決策 | 理由 | 影響 |
|:---|:---|:---|
| **Python Injection Handling** | **Reflection**: 透過 C# 反射注入 Python 代碼。 | 繞過 Dynamo UI 限制，實現真正的腳本注入。 |
| **Workspace Clearing Prevention** | **Upsert**: 實作 Upsert 邏輯。 | 防止因重複創建節點而觸發 `CreateNodeCommand` 重置。 |
| **Incremental Updates** | **Stage-based Verification**: 分階段驗證幾何生成。 | 提高生成穩定性，避免單次大量生成失敗。 |

## 🔄 Memory Bank Patterns

- **Context-First**: 每次對話開始前，必須讀取 Memory Bank。
- **SOP-Driven**: 任何複雜操作 (Deploy, Save, Lessons) 都應有 SOP。
- **Active Documentation**: 文件即程式碼 (Docs-as-Code)。

## 🔌 插件與相依性 (Dependencies)

- **Dynamo Revit**: 3.3+
- **Python**: 3.9+
- **Revit API**: 2024+
