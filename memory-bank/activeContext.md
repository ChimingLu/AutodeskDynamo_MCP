# 當前工作焦點

> **最後更新**: 2026-10-09

## 📍 當前狀態
- **版本**: v3.6 (Node Registry & Connection Patterns)
- **主要工作**: **v3.6 節點知識庫與模式復用** - 實作 `get_node_recipe` 以避免建立節點時的名稱誤區，並透過 `get_node_pattern`/`save_node_pattern`/`capture_node_pattern` 建立可自動驗證、一鍵復用的 Dynamo 節點組合。

## 🎯 近期決策

| 日期 | 決策 | 結果 |
|:---|:---|:---|
| 2026-05-30 | 跨版本安裝支援 | `deploy.ps1` 與驗證腳本強化，支援 Revit 2020-2027，並加入安裝驗證 Skill |
| 2026-06-21 | Mermaid 圖表模式化 | `generate_workspace_mermaid` 新增 `mode`（`pipeline`/`semantic`/`detail`），預設 `pipeline` |
| 2026-10-08 | 建立 Node Registry | 導入 `domain/node_registry.json`，讓 AI 建立節點前有標準答案（建置名稱、埠口順序） |
| 2026-10-08 | 導入 Connection Patterns | 將常用節點邏輯（如 Level/Grid Create）固化為可一鍵執行的 JSON 模式檔 |
| 2026-10-08 | 節點屬性與可變參數增強 | 支援設定 `isInput`/`isOutput` (供 Dynamo Player 用)，並擴充 `inputCount` 到 `List.Create` 等節點 |
| 2026-10-08 | Node.js 版本要求 | 升級 `@hono/node-server` 依賴，明確要求環境 Node.js >= 20 |
| 2026-10-13 | 通用幾何連接模式擴充 | 提煉無套件依賴的高階 3D 幾何與演算法連接模式（頂面過濾、對稱延伸、迭代切面、邊界檢測）存入 Node Registry |
| 2026-10-13 | 實機批次放置連接模式 | 將 4 組幾何連接模式（共 31 節點、29 連線）成功放置到 Dynamo 工作區，自動錯開座標並建立對應顏色群組標籤 |

## 🔄 進行中任務
- [x] 建立並驗證基礎的 `capture_node_pattern` 流程（Level & Grid Create 已實機驗證通過）
- [x] 更新 `README.md` 與 `README_EN.md` 包含 Node Registry 說明
- [x] 擴充更多 Dynamo 常用工作流為 Node Patterns（如 Element.GetParameterValueByName、OpenXML 讀取與匯出模式）
- [x] 提煉實體頂面過濾、線段雙向延伸、DesignScript 多曲線迭代切割曲面、邊界穿越篩選等 4 組連接模式
- [x] 實機驗證並批次放置 4 組幾何連接模式至 Dynamo 工作區並自動建立彩色分組
- [ ] 完善 Custom Node (外掛節點) 的 GUID 映射表（Mapping Table）建置

## ⚠️ 待解決問題
- **BUG-003**: Custom Node (外掛節點) 無法透過名稱字串搜尋/建立。
  - **Workaround**: 已成功使用 GUID 建立。搭配 `get_node_recipe` 可避免名稱誤判。

## 📝 備註
- 目前在建立任何節點圖表前，強烈建議**先呼叫 `get_node_recipe`** 查詢節點建置規則。
- 常見的連續節點操作，應盡量寫成 Pattern 檔案儲存，以減少 Token 浪費並提高可靠度。
- 若有建立動態數量埠口的需求（如 `List.Create`），請使用 `inputCount` 屬性。
