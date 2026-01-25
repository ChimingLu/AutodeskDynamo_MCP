# 穩定性改善變更日誌

## v3.1 (2026-01-25) - UI 現代化與選單整合
### 🔥 重大變更：廢止手動控制節點
- **移除 `StartMCPServer` 與 `StopMCPServer` 節點**：
  - 完全棄用畫布節點控制模式，改由 Dynamo 頂部選單 `BIM Assistant` 統一管理。
  - 理由：解決節點被誤刪除或重複放置導致的連線不穩定問題。
- **全新選單介面**：
  - 新增 `Connect to MCP Server` 開關。
  - 新增 `Auto-Connect on Startup` 功能，確保外掛載入時自動建立連線。
  - 新增 `Status` 即時狀態顯示。
- **文檔全面更新**：
  - 已更新 `GEMINI.md`, `QUICK_REFERENCE.md`, `README_EN.md` 以及所有 SOP 文件。

## v2.5 (2026-01-05) - 連線生命週期與幽靈監聽器解決方案

### 🔥 核心突破：幽靈監聽器 (Ghost Listener) 解決方案

針對在 Revit 內重開 Dynamo 視窗導致的端口佔用與連線錯位，實施了以下重大修復：

#### C# 核心擴充功能 (v2.3 內部版本)
- **強制奪取機制 (Force Takeover)**：
  - 修改 `SimpleHttpServer` 實作靜態實例追蹤。
  - 新實體啟動時，若偵測到同進程內的舊實體，會強制執行 `Stop()` 以釋放端口。
- **生命週期自動清理**：
  - `ViewExtension` 現在會監聽 `DynamoWindow.Closed` 事件。
  - 當用戶關閉 Dynamo 視窗時，會主動停止伺服器並釋放端口。
- **Session 實體化**：
  - `SessionId` 由靜態改為執行個體屬性。
  - 每次伺服器重啟都會產生確定的新 SessionID，解決 AI 無法察覺重啟的問題。
- **新增控制節點**：
  - `MCPControls.StopMCPServer`: 允許手動強制清理髒狀態。

#### Python 伺服器 (server.py)
- **啟發式重啟偵測**：
  - 新增 `_detect_potential_restart()` 邏輯。
  - 偵測到節點數劇減或連線異常時，自動在 `analyze_workspace` 返回中加入警告。

### 📝 文檔更新
- **[QUICK_REFERENCE.md]**: 新增幽靈連線處理 SOP 與重啟序列。
- **[GEMINI.md]**: 納入 SessionID 變動感知與 Ghost Listener 判定規範。

---


## v2.4 (2026-01-05) - 穩定性增強版本

### 🔥 重大改善

#### Python 伺服器 (server.py)
- **強化異常處理**: 將寬泛的 `except Exception` 改為具體異常類型
  - 新增 `subprocess.CalledProcessError` 處理
  - 新增 `UnicodeDecodeError` 處理
  - 使用 `traceback.format_exc()` 詳細記錄錯誤堆疊
  - 異常時返回快取資料提升可用性

- **配置化連線參數**: 從 `mcp_config.json` 讀取超時設定
  - 新增 `connection.timeout_seconds` (預設 5 秒)
  - 新增 `connection.retry_attempts` (預設 3 次)
  - 新增 `connection.health_check_enabled`
  - 向後相容舊版配置檔

- **細分異常類型**: `_check_dynamo_connection()` 改善
  - `HTTPError`: HTTP 狀態碼錯誤
  - `URLError`: 連線失敗或逾時
  - `JSONDecodeError`: 回應格式異常
  - 更具體的錯誤訊息

#### C# 擴充功能

**Logger.cs**:
- **日誌輪替機制**
  - 日誌檔案大小限制: 10MB
  - 自動備份為 `.old.1`, `.old.2`, `.old.3`
  - 最多保留 3 個歷史備份
  - 防止長期運行時日誌無限增長

**GraphHandler.cs**:
- **健康檢查端點** (`action: "health_check"`)
  - 回傳系統狀態 (healthy/unhealthy)
  - 版本資訊、Session ID、Process ID
  - 運行時間統計 (uptimeSeconds)
  - 工作區資訊 (名稱、節點數)
  - 快取狀態 (common nodes、搜尋快取)

### 🧪 測試改善

**新增**: `tests/run_all_tests.py` - 測試自動化框架
- 自動發現並執行測試腳本
- 測試分類支援 (connection, node_search, node_placement)
- 30 秒超時保護
- 詳細測試報告 (成功率、執行時間)
- JSON 格式報告輸出

### 📝 文檔更新

- `README.md`: 新增健康檢查端點使用說明
- `mcp_config.json`: 更新版本資訊和新功能列表

---

## 使用方式

### 健康檢查
```python
import urllib.request, json

req = urllib.request.Request(
    "http://127.0.0.1:5050/mcp/",
    data=json.dumps({"action": "health_check"}).encode(),
    headers={'Content-Type': 'application/json'}
)
response = urllib.request.urlopen(req)
print(response.read().decode())
```

### 執行測試套件
```bash
# 執行所有測試
python tests/run_all_tests.py

# 執行特定類別
python tests/run_all_tests.py connection
```

---

## 升級指引

1. **備份現有配置**
   ```bash
   cp mcp_config.json mcp_config.json.bak
   ```

2. **更新程式碼**
   - 拉取最新變更

3. **重新編譯 C# 擴充功能**
   ```powershell
   .\deploy.ps1
   ```

4. **重啟 Dynamo**
   - 確保新版本擴充功能載入

5. **驗證功能**
   ```bash
   python tests/run_all_tests.py
   ```

---

## 破壞性變更

**無** - 此版本完全向後相容 v2.3

---

## 已知問題

無

---

## 貢獻者

- 穩定性評估與改善實施

---

## 下一版本規劃 (v2.5)

- [ ] 效能監控儀表板
- [ ] 支援多 Dynamo 實例連線
- [ ] API 版本控制 (/v1/mcp/)
