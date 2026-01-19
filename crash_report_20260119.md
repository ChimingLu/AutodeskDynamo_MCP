# 🕵️‍♂️ 斷線事故分析報告 (Post-Mortem Analysis)

**日期**: 2026-01-19  
**事件**: `test_connection.py` 連線失敗 (`[WinError 1225] Connection Refused`)

## 1. 事故現象
在執行連線測試時，Python 用戶端無法連接到 MCP 伺服器。
檢查系統狀態發現：
- 埠 `65296` (MCP) 與 `65535` (Dynamo) **皆未處於監聽狀態**（伺服器已停止服務）。
- 但工作管理員中仍存在一個 **"僵屍" Python 程序 (PID 1804)**，記憶體佔用約 50MB，且無法被強制終止 ("存取被拒")。

## 2. 根本原因分析 (Root Cause Analysis)

這次斷線極有可能是 **"之前的 UI 執行緒崩潰" 的副作用 (Aftershock)**。

1.  **觸發點**: 在修復前，Dynamo 插件因為在背景執行緒修改 UI，拋出了 `NotifyCollectionChanged` 異常。
2.  **連鎖反應**:
    - 這個異常雖然被 Dynamo 全部捕捉 (或導致 Dynamo 內部狀態損壞)，但它可能導致與 Python 伺服器之間的 WebSocket 連線被 **不正常關閉 (Abrupt Closure)**。
    - Python `server.py` 使用 `asyncio` + `websockets`。當面對這種異常的 socket 斷開時，如果沒有完美的例外處理，伺服器的主監聽迴圈 (Serving Loop) 可能會崩潰並退出。
3.  **僵屍化**:
    - 雖然伺服器停止了監聽 (所以 `netstat` 沒東西，連線被拒)，但 Python 直譯器本身可能因為還有殘留的執行緒 (非 Daemon thread) 或被系統鎖定而沒有完全退出，變成了 PID 1804 的僵屍程序。

## 3. 修復與預防

✅ **已完成的修復**:
- 我們已經修復了 Dynamo 端的核心問題 (強制 UI 執行緒執行)，這從源頭上消除了導致斷線的異常。

🛡️ **未來預防措施 (已加入待辦)**:
1.  **增強伺服器健壯性**: 在 `server.py` 中增加更強的 `try-catch` 包裹主監聽迴圈，確保即使發生異常連線也不會導致伺服器停止監聽。
2.  **自動重啟機制**: 建議在 `mcp_config.json` 中啟用 `auto_start_server`，或編寫守護腳本 (Watchdog) 監測 65296 埠，一旦消失即自動重啟。

## 4. 結論
這次斷線是**修復前錯誤的殘餘影響**。既然您已經重啟了正確的伺服器 (PID 30900+)，且 Dynamo 插件也已修復，這個問題不應再頻繁發生。

祝您晚安！明天見！ 🌙
