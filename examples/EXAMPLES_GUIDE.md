# Examples - 使用範例

此資料夾包含 MCP Server 的使用範例，展示如何透過 Python 調用 Dynamo MCP 的各種功能。

## 📂 可用範例

### `run_lib_test.py` - 腳本庫載入與執行範例
展示如何：
1. 連接到 MCP Server
2. 列出可用的腳本庫
3. 載入指定的 Dynamo 腳本（從 `DynamoScripts/`）
4. 執行載入的腳本

**使用方式**：
```bash
python examples/run_lib_test.py
```

**預期流程**：
- 列出 `DynamoScripts/` 中的所有可用腳本
- 載入 `solid_demo.json`
- 在 Dynamo 畫布上執行該腳本

## 🎯 目的

這些範例幫助使用者：
- **快速上手**：了解如何與 MCP Server 互動
- **學習最佳實踐**：查看正確的 API 調用方式
- **客製化開發**：作為基礎修改成自己的工具

## 🔗 相關資源

- **DynamoScripts/**：可重用的 Dynamo 圖形定義（JSON 格式）
- **tests/**：系統功能測試（開發者用）
- **MCP Server**：`server.py` - 核心服務

## 💡 如何新增自己的範例

1. 建立新的 Python 檔案在此資料夾
2. 參考 `run_lib_test.py` 的連接方式
3. 調用需要的 MCP 工具（`list_available_nodes`, `execute_dynamo_instructions` 等）
4. 在此 README 中記錄您的範例

## ⚙️ 前置需求

確保 MCP Server 正在運行：
```bash
python server.py
```

預設連接位址：`http://127.0.0.1:8000/sse`
