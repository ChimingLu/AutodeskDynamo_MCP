# 專案簡介與核心定義 (Project Brief)

> **這份文件是整個 AutodeskDynamo_MCP 專案的基礎，定義了核心目標與範圍。**

## 🎯 專案核心目標
建立一個 **AI 驅動的 Autodesk Dynamo 自動化系統**，透過 Model Context Protocol (MCP) 讓大型語言模型 (LLM) 能夠直接控制、查詢並生成 Dynamo 圖形腳本。

## 💡 核心價值主張
- **自然語言轉腳本 (NL-to-Script)**: 讓使用者透過對話即可生成複雜的幾何與邏輯。
- **即時互動 (Real-time Interaction)**: 支援增量開發 (Incremental Development)，而非一次性生成。
- **強大的自動化 (Robust Automation)**: 解決 Python Script 注入、節點搜尋與連線的底層困難。
- **架構穩定性 (Stability)**: 透過 WebSocket 與 C# ViewExtension 保持穩定的通訊。

## 📂 專案範圍
1.  **Backend (Python Server)**: MCP Bridge，負責將 MCP 指令轉換為 WebSocket 訊息。
2.  **Frontend (Dynamo ViewExtension)**: C# 插件，負責接收指令並操作 Dynamo API。
3.  **Knowledge Base (Memory Bank)**: 結構化的知識管理系統，支援 SOP 與長期記憶。
4.  **Generative Workflows**: 驗證系統能力的實際應用案例。

## 🚫 非目標 (Non-Goals)
- **取代 Dynamo**: 目標是輔助，而非重新發明 Dynamo 引擎。
- **封閉系統**: 必須保持開源與可擴展性。

## 🔑 成功關鍵
1.  **Memory Bank**: 確保 AI 在多次對話中保持上下文 (Context Preservation)。
2.  **SOP**: 透過標準作業程序降低錯誤率。
3.  **Stability**: 解決工作區清空等穩定性問題。
