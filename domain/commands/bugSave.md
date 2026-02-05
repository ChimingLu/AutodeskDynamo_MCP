---
description: 保存當前錯誤狀態供日後分析
---

# /bugSave - 錯誤狀態保存指令

## 行為規範

1. **讀取當前狀態**
   - 執行 `get_graph_status` 取得完整工作區狀態
   - 執行 `get_error_nodes` 取得錯誤節點詳情

2. **生成報告**
   - 時間戳記: `YYYYMMDD_HHmmss`
   - 報告內容:
     - 工作區名稱
     - 節點列表 (含錯誤狀態)
     - 連線列表
     - 錯誤訊息

3. **儲存位置**
   - 路徑: `tests/logs/bug_YYYYMMDD_HHmmss.json`
   - 此目錄已加入 .gitignore

4. **回報用戶**
   ```
   ✅ 錯誤狀態已保存至:
   tests/logs/bug_20260205_205755.json
   
   包含:
   - 12 個節點
   - 8 個連線
   - 2 個錯誤節點
   ```

## 執行範例

```
用戶: bugSave
AI: 正在保存錯誤狀態...
    ✅ 已保存至 tests/logs/bug_20260205_205755.json
```
