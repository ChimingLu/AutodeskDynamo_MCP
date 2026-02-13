# 產品背景與使用者情境 (Product Context)

> **這份文件描述為什麼需要這個專案，以及它解決了什麼問題。**

## 🏗️ 解決的問題 (The Problem)

1.  **Dynamo 操作門檻高**: 初學者難以快速上手，甚至資深使用者在編寫複雜的 Python 腳本時也容易出錯。
2.  **腳本注入困難**: 自動化生成腳本時，如何在不破壞現有節點的情況下注入複雜的 Python 代碼是一個挑戰。
3.  **缺乏穩定的自動化橋樑**: Dynamo 對外部程式的控制缺乏官方支援，需要透過 WebSocket 與 ViewExtension 實現。
4.  **上下文丟失**: AI 在長篇對話中容易忘記之前的指令或生成的邏輯。

## 💡 解決方案 (The Solution)

1.  **MCP-Driven Dynamo Control**: 透過 Model Context Protocol 來標準化指令介面。
2.  **Structured Memory Bank**: 引入 Memory Bank 來管理專案上下文、進度與教訓。
3.  **Reliable Python Injection**: 開發 `GraphHandler.cs` 來處理安全的 Python 代碼注入與節點更新 (Upsert)。
4.  **Incremental Validation**: 透過分段驗證 (Stage-by-Stage Verification) 來穩定生成複雜的 Facade。

## 👤 使用者體驗目標 (User Goals)
1.  **"Just Works" Generation**: 使用者只需描述需求，Dynamo 圖形即可自動生成。
2.  **No Data Loss**: 系统必須具備容錯能力，錯誤操作不應清空使用者的工作區。
3.  **Transparent Validation**: 每個階段的生成都應該是可驗證的。

## 📈 為什麼需要 Memory Bank?
- **Context Preservation**: 讓專案在連續對話中保持連續性。
- **Consistent Development**: 確保 AI 的輸出風格與邏輯一致。
- **Self-Documenting**: 自動產出的文件即為專案的最佳說明書。
