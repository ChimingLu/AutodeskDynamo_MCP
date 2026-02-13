# 失敗檢討報告：Zaha Facade (v3.3)

> **日期**: 2026-02-13
> **結果**: 失敗 (雖然功能運作，但過程與方法未達標)

## ❌ 失敗原因分析

### 1. 策略退縮 (Abandoning Python)
- **問題**: 在遇到工作區清空 Bug 後，為了追求短期穩定，放棄了原本的 "Python Script Automation" 目標，轉而使用 Dynamo 原生節點。
- **後果**: 產出的圖形雜亂、邏輯分散，且未達成使用者對於「Python 自動化」的核心需求。
- **教訓**: **User Intent > Stability Workarounds**。如果目標是 Python，就不能用 Native Nodes 敷衍，必須解決 Python 注入的根本問題。

### 2. 無效的自動化 (Ineffective Automation)
- **問題**: 部署腳本 (Python Deployment) 多次失敗，產生 NullReferenceException，導致節點屬性未更新、連線斷裂。
- **後果**: 最終依賴使用者「手動連線」和「手動修改 Code Block」才完成任務。
- **教訓**: **Manual Fix = Automation Fall**. 自動化腳本必須具備原子性 (Atomicity) 和自我驗證能力，不能依賴使用者收尾。

### 3. Token 效益低落 (Token Waste)
- **問題**: 在偵錯過程中，進行了多次微小的嘗試 (Patch v1, v2, v3...)，而非一次性解決根本問題。
- **教訓**: 在執行修復前，應先在本地 (Local Simulation) 或腦中進行更完整的模擬，減少無效的 `run_command` 次數。

## 🔧 改進計畫 (Action Items)

1.  **Python Injection First**: 確立 Python Script Node 為複雜邏輯的首選載體，不再輕易降級為原生節點。
2.  **Robust Upsert**: C# 的 `Upsert` 邏輯需增強對 `UpdateModelValue` 的錯誤處理，避免因屬性名稱不對應而崩潰。
3.  **Verification Scripts**: 開發更嚴謹的驗證腳本，在通知使用者前先確認圖形完整性 (Connectivity Check)。
