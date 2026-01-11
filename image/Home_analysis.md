---
title: Dynamo 腳本分析報告 - Home
date: 2026-01-11
author: AI Assistant (via Nano Banana Pro)
status: Analysis Complete
---

# 📊 Dynamo 腳本視覺化分析報告

## 📋 腳本資訊快報 (Script Info)

| 項目 | 內容 |
| :--- | :--- |
| **📁 腳本名稱** | **Home** (未儲存的工作區) |
| **🔢 節點總數** | **39** 個節點 |
| **🧠 邏輯複雜度** | ⭐⭐⭐⭐ (中高) - 涉及複雜幾何運算與 Revit 元件建立 |
| **🎯 主要用途** | **自動化樓板建立 (Automated Floor Creation)**<br>透過選取模型元素，分析其實體幾何與邊界框，並進行布林運算（扣除/聯集），最終依據輪廓自動建立樓板。 |
| **🏷️ 關鍵標籤** | `Geometry` `Solid` `Boolean` `Floor` `BoundingBox` |

---

## 📥 輸入參數 (Inputs)

腳本偵測到以下關鍵輸入節點，使用者需在執行前確認：

| 輸入節點名稱 | 類型 | 說明 |
| :--- | :--- | :--- |
| **點選大樓版** | `DSModelElementSelection` | 選擇 Revit 中的參考元素（可能是大樓量體或參考底圖）。 |
| **Boolean** | `BoolSelector` | 布林切換開關，可能用於控制篩選邏輯或執行模式。 |
| **Code Block** | `CodeBlockNodeModel` | 多個程式碼區塊，內含參數設定值（因未見具體代碼，推測為數值或字串常數）。 |

---

## ⚙️ 執行過程 (Execution Process)

系統依據節點邏輯推演的執行步驟如下：

1.  **元素選取**: 使用者透過 `點選大樓版` 節點選擇 Revit 模型中的來源物件。
2.  **幾何擷取**:
    *   透過 `Element.Solids` 提取選取物件的 3D 實體幾何。
    *   透過 `Element.BoundingBox` 取得元素的邊界框，用於快速篩選與碰撞偵測。
3.  **資料篩選與處理**:
    *   使用 `List.Flatten` 攤平清單結構。
    *   使用 `List.FilterByBoolMask` 依據條件（如 `List.Contains` 或 `BoundingBox.Intersects`）篩選出目標幾何。
4.  **幾何布林運算 (核心邏輯)**:
    *   **實體聯集 (`Solid.ByUnion`)**: 將多個零碎實體合併為單一大實體。
    *   **實體差集 (`Solid.DifferenceAll`)**: 從主實體中扣除干涉部分（可能是開口或管線預留孔）。
    *   **幾何炸開 (`Geometry.Explode`)**: 將複雜幾何分解為基礎元件（面/邊）。
5.  **輪廓提取**:
    *   使用 `Surface.PerimeterCurves` 取得運算後實體底面的邊界曲線。
6.  **樓板建立**:
    *   最終呼叫 `Floor.ByOutlineTypeAndLevel`，依據計算出的輪廓線、指定的樓板類型與樓層，在 Revit 中生成實體樓板。

---

## 📤 產出結果 (Outputs)

| 產出類型 | 說明 | 相關節點 |
| :--- | :--- | :--- |
| **Revit 樓板** | 自動生成的樓板元件 | `Floor.ByOutlineTypeAndLevel` |
| **幾何實體** | 運算過程中的 3D 實體預覽 | `Solid.ByUnion`, `Solid.DifferenceAll` |

---

## 📦 必要外掛清單 (Dependencies)

執行此腳本需要以下環境或套件：

- **Dynamo Core** (內建)
- **Dynamo Revit** (內建 Revit 節點)
- **DynamoMCPListener** (用於 MCP 通訊與控制)

---

## 📊 邏輯流程圖 (Logic Flowchart)

以下為依據節點功能重建的邏輯拓樸圖：

```mermaid
graph TD
    %% 定義樣式
    classDef input fill:#f9f,stroke:#333,stroke-width:2px;
    classDef process fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef geometry fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef output fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#000;

    subgraph Inputs [📥 輸入階段]
        Sel["點選大樓版 (Element Selection)"]:::input
        Bool["Boolean 開關"]:::input
        Params["Code Block (參數)"]:::input
    end

    subgraph GeometryOps [📐 幾何運算核心]
        GetSolid["Element.Solids (取得實體)"]:::geometry
        GetBB["Element.BoundingBox (邊界框)"]:::geometry
        Union["Solid.ByUnion (實體聯集)"]:::geometry
        Diff["Solid.DifferenceAll (實體差集)"]:::geometry
        Explode["Geometry.Explode (幾何分解)"]:::geometry
        SrfCrv["Surface.PerimeterCurves (輪廓線)"]:::geometry
    end

    subgraph DataProcess [🔄 資料處理]
        Filter["List.FilterByBoolMask (篩選)"]:::process
        Flatten["List.Flatten (攤平)"]:::process
        Intersect["BoundingBox.Intersects (交集檢查)"]:::process
    end

    subgraph Creation [🏗️ 建立元件]
        CreateFloor["Floor.ByOutlineTypeAndLevel (建立樓板)"]:::output
    end

    %% 邏輯連接 (推測)
    Sel --> GetSolid & GetBB
    GetSolid --> Union
    GetBB --> Intersect
    Union --> Diff
    Diff --> Explode
    Explode --> SrfCrv
    SrfCrv --> CreateFloor
    Params --> CreateFloor
    Filter --> Diff

```

---

> **💡 AI 分析註記**：
> 此腳本為典型的「幾何分析生成」腳本。使用了進階的實體布林運算 (`Solid Operations`) 處理複雜形狀，這在處理不規則邊界樓板或需自動扣除開口的場景中非常強大。
> 建議檢查 `List.FilterByBoolMask` 的遮罩邏輯，即確保篩選出的輪廓線是封閉且平面的，否則 `Floor.ByOutlineTypeAndLevel` 可能會失敗。
