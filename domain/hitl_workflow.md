---
title: "Human-in-the-Loop 工作流程 (Dry Run 機制)"
version: "1.0"
last_update: "2026-02-03"
applies_to: ["server.py", "execute_dynamo_instructions"]
---

# Human-in-the-Loop 工作流程

## 概述

此文檔說明 Dynamo MCP 的 **Dry Run (預覽執行)** 機制，讓 AI Agent 在實際修改工作區前先進行驗證。

## 使用場景

1. **複雜腳本生成**：在創建大量節點前，先預覽完整結構
2. **參數驗證**：確認座標、連線是否正確
3. **風險評估**：偵測潛在問題（位置重疊、未連接節點）

## 調用方式

```json
{
  "name": "execute_dynamo_instructions",
  "arguments": {
    "instructions": "{\"nodes\": [...], \"connectors\": [...]}",
    "dryRun": true,
    "base_x": 0,
    "base_y": 0
  }
}
```

## 回傳格式

### 成功預覽

```json
{
  "status": "dry_run",
  "summary": {
    "nodesToCreate": 5,
    "connectorsToCreate": 3,
    "estimatedBounds": {
      "minX": 50,
      "maxX": 550,
      "minY": 100,
      "maxY": 400
    }
  },
  "nodes": [
    {"id": "pt1", "name": "Point.ByCoordinates", "position": {"x": 300, "y": 200}}
  ],
  "connectors": [
    {"from": "pt1", "to": "line1", "fromPort": 0, "toPort": 0}
  ],
  "warnings": [
    "警告: 節點 'n2' 與 'n1' 位置重疊",
    "注意: 節點 'sphere1' 未連接任何其他節點"
  ]
}
```

### 錯誤回傳

```json
{
  "status": "error",
  "message": "JSON 解析錯誤: Expecting property name enclosed in double quotes"
}
```

## 警告類型

| 警告類型 | 說明 | 建議處理 |
|:---|:---|:---|
| **位置重疊** | 兩個節點座標完全相同 | 調整 `x` 或 `y` 值 |
| **未連接節點** | 節點不在任何連線中 | 確認是否需要連線 |

## 最佳實踐

1. **先 Dry Run，後執行**
   ```python
   # 步驟 1：預覽
   preview = execute_dynamo_instructions(json, dryRun=True)
   
   # 步驟 2：確認無警告後執行
   if not preview["warnings"]:
       result = execute_dynamo_instructions(json, dryRun=False)
   ```

2. **處理警告後重試**
   - 若有位置重疊：在 `base_x` 或 `base_y` 加上偏移量
   - 若有未連接節點：檢查 `connectors` 陣列是否遺漏

## 限制

- Dry Run **無法模擬**：
  - Python Script 節點的執行結果
  - 外部 API 節點的回傳值
  - 實際幾何運算（如布林差集的有效性）

- Dry Run **可以驗證**：
  - JSON 語法正確性
  - 節點名稱有效性
  - 連線埠位參照正確性
  - 座標範圍合理性
