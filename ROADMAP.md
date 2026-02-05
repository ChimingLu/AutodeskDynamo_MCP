# 🗺️ Autodesk Dynamo MCP - 開發路線圖

> **語言 / Language:** [繁體中文](ROADMAP.md) | [English](ROADMAP_EN.md)

本文件概述 Autodesk Dynamo MCP Integration Project 的未來發展方向與規劃。

---

## 📍 當前版本

**v3.1** (2026-01-25) - UI 現代化與選單整合
**v3.2** (In Progress) - Memory Bank 知識管理與 SOP 系統

---

## 🎯 戰略定位

**Revit MCP vs. Dynamo MCP 分工**

| Agent | 專注領域 |
|:---:|:---|
| **Revit MCP** | BIM 資料庫管理、屬性讀寫、Transaction 處理 |
| **Dynamo MCP** | **幾何運算核心 (Geometry Library)** 優勢利用、透過視覺化編程驗證複雜執行邏輯 |

---

## 🏗️ 功能規劃總覽

本專案依據**開發流程（Development Lifecycle）**與**功能屬性**，規劃為四大面向：

```mermaid
graph LR
    A[智慧輔助開發與除錯] --> B[知識增強與個人化學習]
    B --> C[高階功能擴展]
    C --> D[產品化與生態系協作]
```

---

## 一、智慧輔助開發與除錯 (Intelligent Development & Debugging)

> 解決開發當下的痛點，提升程式碼品質與邏輯正確性。

### 🔧 智慧除錯與邏輯優化
- [ ] 主動偵測工作區（Workspace）的錯誤
- [ ] 自動修復斷裂或錯誤的連線
- [ ] 識別效能低落的節點組合
- [ ] 建議替換為最佳實踐（Best Practice）寫法

### � 工作區標準化整理 (IPO 模式)
- [ ] 解決「義大利麵條式（Spaghetti Code）」亂象
- [ ] 自動依據 **Input → Process → Output** 分群
- [ ] 節點視覺化顏色標記
- [ ] 建立易於維護的程式架構

### 📊 List (清單) 邏輯深度解析
- [ ] 針對資料流問題（Lacing, Levels）提供視覺化模擬
- [ ] 運算前展示 Shortest/Longest/Cross Product 結構差異
- [ ] 避免資料錯位問題

---

## 二、知識增強與個人化學習 (Knowledge & Personalization)

> 將 Agent 定位為導師，解決資訊焦慮並傳承經驗。

### 🔍 解決節點檢索與應用痛點
- [x] 精準的節點推薦與使用範例查詢 *(v3.1 已實現基礎版)*
- [x] 外掛套件節點搜尋與放置 *(v3.1 已實現，支援 BimorphNodes, Clockwork, Data-Shapes, Archi-lab)*
- [ ] 解決「不知道用什麼節點」的資訊焦慮
- [ ] 解決「不知道有什麼外掛」的探索困難

### 🧠 Memory Bank 專案大腦 (v3.2)
- [x] **Memory Bank 架構**：建立 `memory-bank/` 結構化知識庫 (`activeContext`, `progress`)
- [x] **SOP 知識庫**：將操作指令標準化為 SOP 文件 (`domain/commands/`)
- [ ] 自動更新機制：對話結束後自動更新 Context

### 🧠 AI Agent 學習與個人化知識庫
- [ ] 讀取團隊過去的 `.dyn` 檔案（Legacy Data）
- [ ] 學習特定的節點使用習慣與獨門技巧
- [ ] 提供符合使用者風格（Context-Aware）的建議

### 📚 教育訓練與即時導師
- [ ] 針對原生節點提供「做中學（Learning by Doing）」即時教學
- [ ] 解釋節點背後的運作原理
- [ ] 協助新手跨越技術門檻

---

## 三、高階功能擴展 (Advanced Capabilities)

> 協助使用者突破 Dynamo 原生限制，進行複雜運算。

### 🐍 Python Node 生成與 API 整合
- [x] 自動編寫 Python Script 處理原生節點無法執行的任務 *(v3.1 已實現)*
- [x] Python 代碼注入與 CPython3 引擎設置 *(v3.1 已實現)*
- [ ] 外部 API 串接（網路資料、AI 服務）
- [ ] 複雜程式語法封裝

### 🎨 衍生式設計 (Generative Design) 協作
- [ ] 透過對話釐清設計目標、變數與限制條件
- [ ] 自動產出符合衍生式設計規範的腳本
- [ ] 協助使用者進行幾何最佳化運算

---

## 四、產品化與生態系協作 (Productization & Ecosystem)

> 關注程式交付後的「易用性」以及與其他系統的整合。

### 📄 意圖理解與自動化文檔
- [ ] 分析腳本業務目的
- [ ] 自動生成技術說明文件
- [ ] 生成終端使用者操作手冊
- [ ] 實現「程式寫完，文件也同時完成」

### 🎮 Dynamo Player 智慧封裝
- [ ] 扮演「智慧封裝者」角色
- [ ] 自動識別並建議 Input/Output 節點
- [ ] 優化 Player 介面
- [ ] 技術參數重新命名為友善提示文字
- [ ] 協助群組排序

### 🤝 多 Agent 協作生態系
- [ ] 與 **Revit MCP** 分工合作
- [ ] Revit MCP 負責資料庫讀寫
- [ ] Dynamo MCP 負責複雜幾何運算與邏輯處理
- [ ] 形成完整工作流

---

## 📊 版本里程碑

| 版本 | 主要功能 | 狀態 |
|:---:|:---|:---:|
| **v3.2** | Memory Bank 知識管理、SOP 系統 | 🔄 進行中 |
| **v3.3** | 效能監控儀表板、API 版本控制 | 📋 待開始 |
| **v3.3** | 多實例支援、工作區快照 | 📋 待開始 |
| **v4.0** | 智慧除錯、IPO 模式整理 | 📋 待開始 |
| **v4.1** | 節點推薦增強、個人化知識庫 | 📋 待開始 |
| **v4.2** | List 邏輯視覺化、教育訓練模組 | 📋 待開始 |
| **v5.0** | 衍生式設計協作 | 📋 待開始 |
| **v5.1** | 自動化文檔、Player 智慧封裝 | 📋 待開始 |
| **v6.0** | 多 Agent 協作生態系 | 💭 願景 |

**狀態說明：**
- ✅ 已完成
- 🔄 規劃中
- 📋 待開始
- 💭 願景

---

## � 社群提案

歡迎透過 GitHub Issues 提交功能建議！請使用 `enhancement` 標籤。

**如何貢獻：**
1. 開啟 Issue 描述您的想法
2. 討論可行性與實作方式
3. 提交 Pull Request

---

## �📝 更新紀錄

- **2026-02-05**: 新增 v3.2 Memory Bank 與 SOP 系統規劃
- **2026-02-03**: 整合四大面向功能構想，重構 RoadMap 架構

---

> 此 RoadMap 會根據專案進展與社群反饋持續更新。
