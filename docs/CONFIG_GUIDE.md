# 📝 MCP 配置檔案使用指南

## 📋 目錄
- [快速開始](#快速開始)
- [配置檔案結構](#配置檔案結構)
- [常見修改場景](#常見修改場景)
- [自動部署機制](#自動部署機制)
- [故障排除](#故障排除)

---

## 🚀 快速開始

### 第一次使用

1. **編輯配置模板**
   ```powershell
   # 使用任何文字編輯器打開模板檔案
   notepad mcp_config.template.jsonc
   ```

2. **修改標記為 🔧 的項目**
   - `user_info.name`: 您的使用者名稱
   - `server.port`: 預設為 65296 (MCP Bridge 埠號)

3. **執行部署腳本**
   ```powershell
   .\deploy.ps1
   ```

   部署腳本會自動：
   - ✅ 將模板轉換為 `mcp_config.json`
   - ✅ 建置 C# 專案
   - ✅ 部署至 Dynamo 套件資料夾
   - ✅ 複製配置檔案

---

## 📂 配置檔案結構

### 檔案關係

```
專案根目錄/
├── mcp_config.template.jsonc    ← 🔧 您應該編輯這個檔案（帶註解）
├── mcp_config.json               ← ⚠️  自動生成，請勿手動修改
└── scripts/
    └── update_config.ps1         ← 轉換腳本
```

### 為什麼需要兩個檔案？

| 檔案 | 用途 | 可否編輯 |
|:---|:---|:---:|
| `mcp_config.template.jsonc` | **開發模板**<br>包含詳細的繁體中文註解，方便理解與修改 | ✅ 是 |
| `mcp_config.json` | **程式讀取**<br>由模板自動生成的純 JSON，程式實際載入的檔案 | ❌ 否 |

---

## 🔧 常見修改場景

### 場景 1：修改伺服器埠號

**問題**：啟動 `server.py` 時提示 `Address already in use`

**解決方案**：

1. 打開 `mcp_config.template.jsonc`
2. 找到 `server.port` 欄位（約第 58 行）
3. 修改為未被佔用的埠號（例如：`5051`）
   ```jsonc
   "server": {
       "host": "127.0.0.1",
       "port": 5051,  // 🔧 修改點
       "url_path": "/mcp/"
   }
   ```
4. 執行 `.\deploy.ps1` 套用變更

---

### 場景 2：啟用除錯模式

**需求**：需要更詳細的記錄訊息來排查問題

**解決方案**：

1. 修改 `rules.log_level`：
   ```jsonc
   "rules": {
       "log_level": "DEBUG"  // 🔧 從 INFO 改為 DEBUG
   }
   ```

2. 可選：保留臨時檔案以便檢查
   ```jsonc
   "keep_temp_files": true
   ```

---

### 場景 3：支援多個 Dynamo 版本

**需求**：同時在 Dynamo 3.2 和 3.3 上測試

**解決方案**：

1. 修改 `auto_deployment.target_dynamo_versions`：
   ```jsonc
   "auto_deployment": {
       "target_dynamo_versions": ["3.3", "3.2"],  // 🔧 按優先順序排列
       "backup_before_deploy": true
   }
   ```

2. 部署腳本會自動偵測並選擇最高版本

---

## 🚀 自動部署機制

### 工作流程

```mermaid
graph LR
    A[編輯 template.jsonc] --> B[執行 deploy.ps1]
    B --> C[轉換為 mcp_config.json]
    C --> D[建置 C# 專案]
    D --> E[部署至 Dynamo]
    E --> F[複製配置檔案]
    F --> G[部署完成]
```

### 手動轉換配置（不部署）

如果只想更新配置檔案而不重新部署：

```powershell
python scripts\update_config.py
```

或使用 PowerShell 調用：

```powershell
python .\scripts\update_config.py
```

---

## 🛡️ 故障排除

### ❌ 錯誤：JSON 格式驗證失敗

**症狀**：執行 `deploy.ps1` 時提示 `JSON 格式驗證失敗`

**原因**：模板檔案的 JSON 語法錯誤

**檢查清單**：
- [ ] 所有字串都用雙引號 `"` 包裹（不能用單引號 `'`）
- [ ] 物件和陣列的最後一個項目後**不能**有逗號
- [ ] 未關閉的括號 `{}`、`[]`

**工具**：使用線上 JSON 驗證器（移除註解後）：https://jsonlint.com/

---

### ⚠️ 警告：找不到 update_config.ps1

**症狀**：部署時跳過配置更新步驟

**原因**：`scripts/update_config.ps1` 不存在或被移動

**解決**：
```powershell
# 檢查檔案是否存在
Test-Path .\scripts\update_config.ps1

# 如果不存在，請從專案倉庫重新取得該檔案
```

---

### 🔍 如何確認配置已套用？

**方法 1**：檢查時間戳記
```powershell
Get-Item .\mcp_config.json | Select-Object LastWriteTime
```

**方法 2**：檢查伺服器記錄
```powershell
# 啟動 server.py 後，檢查記錄檔
Get-Content logs\mcp_server.log -Tail 20
```

伺服器啟動時會記錄載入的配置參數。

---

## 📚 延伸閱讀

- [GEMINI.md](../GEMINI.md) - AI 協作規範
- [README.md](../README.md) - 專案整體說明
- [domain/startup_checklist.md](../domain/startup_checklist.md) - 啟動檢查清單

---

## 🆘 需要協助？

如有問題，請：
1. 查閱 [domain/troubleshooting.md](../domain/troubleshooting.md)
2. 執行 `/bug` 指令回報問題
3. 檢查 GitHub Issues
