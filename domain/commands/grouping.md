# 節點分組功能 (Node Grouping)

## 簡介
此功能允許 AI Agent 透過 `create_group` 指令，將 Dynamo 工作區中的特定節點群組化 (Group)，並設定標題、描述與顏色。這有助於自動化整理大型腳本，提升可讀性。

## 工具規格：`create_group`

| 參數 | 類型 | 必填 | 預設值 | 說明 |
|:---|:---|:---|:---|:---|
| `nodeIds` | List\<string\> | ✅ 是 | - | 要加入群組的節點 ID 清單。可使用 GUID 字串。 |
| `title` | string | ❌ 否 | "New Group" | 群組上方的標題文字。 |
| `description` | string | ❌ 否 | "" | 滑鼠停留在群組時顯示的說明文字。 |
| `color` | string | ❌ 否 | "#FFC1D5E0" | 群組背景顏色 (Hex 格式)。 |

## 使用範例

### 1. 透過 Python 腳本呼叫

```python
import asyncio
import websockets
import json

async def group_nodes():
    uri = "ws://127.0.0.1:65296"
    async with websockets.connect(uri) as websocket:
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create_group",
                "arguments": {
                    "nodeIds": ["GUID-1", "GUID-2", "GUID-3"],
                    "title": "幾何運算核心",
                    "description": "負責處理核心幾何生成的邏輯",
                    "color": "#FF88CC00"  # 綠色
                }
            },
            "id": 1
        }
        await websocket.send(json.dumps(request))
        print(await websocket.recv())

asyncio.run(group_nodes())
```

### 2. Agent 指令範例

> "請幫我把所有負責數學運算的節點分組，群組名稱叫 'Math Logic'，顏色設為藍色。"

Agent 會先執行 `analyze_workspace` 找到相關節點的 GUID，然後呼叫 `create_group`：

```json
{
  "name": "create_group",
  "arguments": {
    "nodeIds": ["3c0a123b...", "88263286..."],
    "title": "Math Logic",
    "color": "#FFADD8E6"
  }
}
```

## 注意事項
- **需要重啟**: C# 插件更新後，必須重啟 Dynamo 才能生效。
- **ID 準確性**: `nodeIds` 必須是工作區內真實存在的 GUID。建議先執行 `analyze_workspace` 確認。
