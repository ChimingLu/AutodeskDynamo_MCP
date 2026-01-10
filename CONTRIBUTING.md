# 貢獻指南 (Contributing Guide)

感謝您對 Autodesk Dynamo MCP Integration Project 的興趣！我們歡迎各種形式的貢獻。

## 如何貢獻

### 回報問題 (Reporting Issues)

如果您發現 Bug 或有功能建議，請：

1. 先搜尋 [Issues](../../issues) 確認問題尚未被回報
2. 建立新的 Issue，並提供以下資訊：
   - **環境資訊**: Dynamo 版本、Revit 版本、Windows 版本
   - **重現步驟**: 詳細描述如何重現問題
   - **預期行為**: 您期望發生什麼
   - **實際行為**: 實際發生了什麼
   - **錯誤訊息**: 如果有的話，請附上完整的錯誤訊息或日誌檔 (`DynamoMCP.log`)

### 提交程式碼 (Pull Requests)

我們歡迎 Pull Requests！請遵循以下步驟：

1. **Fork 專案** 並 clone 到本地
2. **建立分支**: `git checkout -b feature/your-feature-name`
3. **進行修改** 並遵循程式碼風格指南
4. **測試您的修改**: 確保所有功能正常運作
5. **提交變更**: `git commit -m "Add: your feature description"`
6. **推送分支**: `git push origin feature/your-feature-name`
7. **建立 Pull Request** 並詳細描述您的修改

### 程式碼風格指南

#### C# 程式碼
- 使用 4 個空格縮排
- 遵循 [Microsoft C# Coding Conventions](https://docs.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions)
- 類別與方法加上 XML 文件註解
- 使用有意義的變數與方法名稱

#### Python 程式碼
- 遵循 [PEP 8](https://pep8.org/) 風格指南
- 使用 4 個空格縮排
- 函數加上 docstring 說明
- 使用 type hints

### 新增常用節點

如果您想加入新的常用節點到 `common_nodes.json`：

1. 確認節點在 Dynamo 中確實存在且常用
2. 遵循現有的 JSON 格式：
   ```json
   {
       "name": "NodeName",
       "fullName": "Full.Namespace.NodeName",
       "description": "Clear description of what this node does",
       "inputs": ["input1", "input2"],
       "outputs": ["output1"]
   }
   ```
3. 按字母順序插入
4. 在 PR 中說明為何此節點應該被加入

### 新增腳本範例

如果您想貢獻新的 Dynamo 腳本範例：

1. 將 JSON 檔案放在 `DynamoScripts/` 目錄
2. 遵循命名規範: `功能_描述.json` (例如 `wall_basic.json`)
3. 包含 `description` 欄位說明腳本用途
4. 確保腳本在 Dynamo 中能正常執行
5. 更新 README.md 的腳本清單表格

## 開發環境設定

### 必要工具
- Visual Studio 2022 或 Visual Studio Code
- .NET 8 SDK
- Python 3.8+
- Autodesk Revit (含 Dynamo)

### 本地開發流程

1. Clone 專案:
   ```bash
   git clone https://github.com/your-username/AutodeskDynamo_MCP.git
   cd AutodeskDynamo_MCP
   ```

2. 安裝 Python 依賴:
   ```bash
   pip install mcp
   ```

3. 編譯 C# 專案:
   ```bash
   cd DynamoViewExtension
   dotnet build
   ```

4. 部署到 Dynamo:
   ```powershell
   .\deploy.ps1
   ```

## 測試

在提交 PR 前，請確保：

- [ ] C# 專案能成功編譯
- [ ] Python Server 能正常啟動
- [ ] 至少測試一個範例腳本能正常執行
- [ ] 沒有破壞現有功能
- [ ] 新增的程式碼有適當的錯誤處理

## 授權

提交貢獻即表示您同意您的程式碼將以 Apache License 2.0 授權。

## 需要幫助？

如果您有任何問題，歡迎：
- 在 Issues 中提問
- 查看現有的 Pull Requests 作為參考
- 閱讀 [README.md](README.md) 了解專案架構

感謝您的貢獻！🎉
