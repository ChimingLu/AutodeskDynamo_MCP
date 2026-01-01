# Tests - 測試腳本

此資料夾包含 MCP Server 功能的測試腳本，用於開發與驗證系統運作。

## 📂 測試腳本列表

### 🔍 節點搜尋測試
- **`list_nodes_test.py`**：測試搜尋 Dynamo 節點功能
- **`find_all.py`**：列出所有可用節點（特別篩選 Clockwork 和 Aqua）
- **`search_aqua.py`**：搜尋特定節點（Aqua）
- **`search_clockwork.py`**：搜尋 Clockwork 套件節點
- **`search_color.py`**：搜尋顏色相關節點

### 🏗️ 節點放置測試
- **`place_aqua.py`**：放置 Color.Aqua 節點
- **`place_aqua_full.py`**：放置 Aqua 節點（完整版本）
- **`place_aqua_simple.py`**：放置 Aqua 節點（簡化版本）

### 📊 系統測試
- **`check_workspace.py`**：分析 Dynamo 工作區狀態
- **`performance_test.py`**：效能測試與 Token 消耗分析

## 🎯 目的

這些測試腳本用於：
- **驗證功能**：確保 MCP Server 各項功能正常運作
- **除錯開發**：快速測試特定功能是否正確
- **效能監控**：追蹤系統效能與資源消耗

## 🔧 使用方式

執行任一測試腳本：
```bash
# 測試節點搜尋
python tests/list_nodes_test.py

# 測試節點放置
python tests/place_aqua.py

# 效能測試
python tests/performance_test.py

# 檢查工作區
python tests/check_workspace.py
```

## ⚠️ 注意事項

- 這些是**開發測試用**腳本，不適合作為終端使用者範例
- 執行前確保 MCP Server 正在運行（`python server.py`）
- 部分測試需要 Dynamo 已開啟且載入特定套件（如 Clockwork）

## 🆚 與 examples/ 的差異

| 特性 | tests/ | examples/ |
|------|--------|-----------|
| **目的** | 驗證系統功能 | 展示使用方式 |
| **對象** | 開發者 | 終端使用者 |
| **內容** | 特定功能測試 | 完整使用流程示範 |
| **穩定性** | 可能頻繁變動 | 相對穩定 |
