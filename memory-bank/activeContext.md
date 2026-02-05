# 當前工作焦點

> **最後更新**: 2026-02-05

## 📍 當前狀態
- **版本**: v3.1
- **主要工作**: Memory Bank 架構建置完成

## 🎯 近期決策

| 日期 | 決策 | 結果 |
|:---|:---|:---|
| 2026-02-04 | Memory Bank 架構設計 | 採用 `memory-bank/` + `domain/commands/` 結構 |
| 2026-02-04 | GEMINI.md 精簡策略 | 核心教訓保留摘要，詳情遷移至 `lessons/` |
| 2026-02-04 | 斜線指令 SOP 化 | 每個指令都有獨立的 SOP 文件 |
| 2026-02-05 | MCP Server 穩定性修復 | 解決 asyncio 衝突與幽靈連線問題 |
| 2026-02-05 | Autotest 規範化 | 建立標準測試流程 SOP |

## 🔄 進行中任務
- [x] Memory Bank 目錄結構建立
- [x] 核心文件創建 (activeContext, progress, techStack)
- [x] 斜線指令 SOP 建立 (9/9 完成)
- [ ] GEMINI.md 重構 (持續進行)
- [ ] MCP Server 穩定性測試與優化
- [ ] README 文件同步更新 (中英文)

## ⚠️ 待解決問題
(無)

## 📝 備註
- Memory Bank 運作規範將整合至 GEMINI.md
- 所有 AI（Antigravity、Gemini CLI、Claude）都使用同一份規範
