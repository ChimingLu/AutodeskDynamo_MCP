# 當前工作焦點

> **最後更新**: 2026-02-22

## 📍 當前狀態
- **版本**: v3.4 (Enhanced Analysis & Stability)
- **主要工作**: **v3.5 節點分組與穩定性優化** - 正在驗證 `create_group` 在不同場景下的穩定性，並計劃建立外掛 GUID 映射表以提升開發效率。

## 🎯 近期決策

| 日期 | 決策 | 結果 |
|:---|:---|:---|
| 2026-02-19 | 修復連線逾時 Bug | 將 `cleanup_stale_sessions` 預設值由 30s 提高至 300s，避免分析大型圖表時斷線 |
| 2026-02-19 | 實作 /image 視覺化分析 | 成功解析大型圖表，並產出 Mermaid 關係圖與技術文檔 |
| 2026-02-22 | 倉儲結構重組 | 將分散的腳本與日誌歸位至 `tools/` 與 `logs/`，並清理根目錄 |
| 2026-02-22 | 更新 Memory Bank | 同步專案狀態至 v3.4，並準備邁向 v3.5 |

## 🔄 進行中任務
- [x] 倉儲結構清理 (Moving files to `tools/`, `logs/`, `trials/`)
- [x] 更新 `README.md` 與 `README_EN.md` 至 v3.4
- [ ] 驗證 `create_group` 功能穩定性
- [ ] 建立 Clockwork GUIDs 建立為映射表 (Mapping Table)

## ⚠️ 待解決問題
- **BUG-003**: Custom Node (外掛節點) 無法透過名稱字串搜尋/建立。
  - **Workaround**: 已成功使用 GUID 建立。長期目標是建立 Mapping Table。

## 📝 備註
- 系統核心功能穩定，分析能力強化後可處理超過 100 個節點的複雜圖表。
- 建議在未來專案中優先使用原生節點，若必須使用外掛，請先取得其 GUID。
