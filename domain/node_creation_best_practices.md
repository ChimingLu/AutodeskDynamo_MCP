# 節點創建最佳實踐

## 核心原則：原生節點優先 (Native Node First)

**前提**：本專案致力於讓使用者能夠看到清晰的、視覺化的節點流程，而非將所有邏輯隱藏在 Code Block 中。

### ✅ 推薦做法

#### 1. 使用明確指定的 Overload（最安全）

```json
{
  "nodes": [{
    "name": "Point.ByCoordinates",
    "overload": "3D",
    "params": {"x": 0, "y": 0, "z": 100},
    "x": 300, "y": 300
  }]
}
```

**優點**：
- 明確、可預測
- 避免歧義
- 適合複雜場景

#### 2. 使用自動推斷（簡潔）

```json
{
  "nodes": [{
    "name": "Point.ByCoordinates",
    "params": {"x": 0, "y": 0, "z": 100},  // 有 z → 自動選 3D
    "x": 300, "y": 300
  }]
}
```

**優點**：
- JSON 更簡潔
- 系統自動判斷

**推斷規則**：
- `Point.ByCoordinates`: 有 `z` 參數 → 3D，否則 → 2D
- `Vector.ByCoordinates`: 有 `z` 參數 → 3D，否則 → 2D

#### 3. 模組化 Code Block（避免巨型單一區塊）

**❌ 不好的做法**：
```json
{
  "nodes": [{
    "name": "Number",
    "value": "p1=Point.ByCoordinates(0,0,0); p2=Point.ByCoordinates(100,0,0); line=Line.ByStartPointEndPoint(p1,p2); solid=line.ExtrudeAsSolid(50);"
  }]
}
```

**✅ 推薦做法**：
```json
{
  "nodes": [
    {
      "id": "base_points",
      "name": "Number",
      "value": "[Point.ByCoordinates(0,0,0), Point.ByCoordinates(100,0,0)];",
      "x": 100, "y": 100
    },
    {
      "id": "line",
      "name": "Number",
      "value": "Line.ByStartPointEndPoint(base_points[0], base_points[1]);",
      "x": 300, "y": 100
    },
    {
      "id": "solid",
      "name": "Number",
      "value": "line.ExtrudeAsSolid(50);",
      "x": 500, "y": 100
    }
  ],
  "connectors": [
    {"from": "base_points", "to": "line", "fromPort": 0, "toPort": 0},
    {"from": "line", "to": "solid", "fromPort": 0, "toPort": 0}
  ]
}
```

**優點**：
- 易於 Debug（可逐段檢查）
- 可視化流程清晰
- 可重複使用中間結果

---

## Code Block 使用時機

**僅在以下情況使用 Code Block**：

1. **簡單數值運算**
   ```json
   {"name": "Number", "value": "100 * 2 + 50;"}
   ```

2. **陣列建立**
   ```json
   {"name": "Number", "value": "0..10..1;"}
   ```

3. **無法用原生節點表達的複雜邏輯**
   ```json
   {"name": "Number", "value": "p.Translate(Vector.ByCoordinates(x_offset, 0, 0));"}
   ```

4. **臨時測試與原型**（非正式腳本）

---

## 節點創建策略

| 策略 | 使用情境 | 範例 |
|:---|:---|:---|
| **NATIVE_DIRECT** | 無 Overload 歧義的節點 | `Line.ByStartPointEndPoint`, `Circle.ByCenterPointRadius` |
| **NATIVE_WITH_OVERLOAD** | 有多個版本的節點 | `Point.ByCoordinates` (2D/3D), `Vector.ByCoordinates` |
| **CODE_BLOCK** | 數值輸入、運算式、Fallback | `Number` 節點（實際上是 Code Block） |
| **PYTHON_SCRIPT** | Python 腳本節點（未來支援） | - |
| **CUSTOM_NODE** | .dyf 自訂節點（未來支援） | - |
| **ZERO_TOUCH** | DLL 節點（未來支援） | - |

策略詳細定義請參考：[`domain/node_creation_strategy.json`](../domain/node_creation_strategy.json)

---

## 故障排除

### Q: 創建 `Point.ByCoordinates` 時只有 2 個輸入埠

**原因**：系統選到了 2D 版本。

**解決方案**：
1. **明確指定 3D**：
   ```json
   {"name": "Point.ByCoordinates", "overload": "3D", "params": {...}}
   ```
2. **確保參數包含 z**：
   ```json
   {"name": "Point.ByCoordinates", "params": {"x": 0, "y": 0, "z": 100}}
   ```

### Q: 複雜幾何創建失敗

**建議**：
1. 先檢查是否有現成的腳本庫範例：`get_script_library`
2. 將複雜幾何拆解為多個模組化步驟
3. 逐段測試，確認每個步驟的輸出

---

## 腳本庫最佳實踐

### 何時儲存至腳本庫

- ✅ 經過測試且穩定的幾何定義
- ✅ 可參數化的常用圖形（如網格、陣列）
- ✅ 複雜的節點組合
- ❌ 臨時測試代碼
- ❌ 高度客製化的一次性腳本

### 命名規範

- 使用描述性名稱：`grid_10x10`, `parametric_wall`
- 小寫 + 底線
- 不包含副檔名

### 參數化範例

```python
# 載入腳本並指定參數
content = load_script_from_library(
    "parametric_grid",
    base_x=500,  # 偏移至 (500, 0)
    base_y=0
)
execute_dynamo_instructions(content)
```

---

## 相關資源

- 📖 [完整實作計劃](../implementation_plan.md)
- 🔧 [故障排除 SOP](troubleshooting.md)
- 🎯 [快速參考](../QUICK_REFERENCE.md)
- 📊 [節點策略配置](node_creation_strategy.json)
