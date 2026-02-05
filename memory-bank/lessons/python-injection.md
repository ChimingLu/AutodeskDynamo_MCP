---
id: 11
title: "Python Script 反射注入的三重保障"
date: 2026-01-24
severity: HIGH
---

# 核心教訓 #11：Python Script 反射注入的三重保障

> **最後更新**: 2026-01-24  
> **突破意義**: 徹底解決 Dynamo 3.3 的 Python 節點代碼注入與 UI 同步問題

---

## 背景問題

Dynamo 3.3 中，使用標準的 `UpdateModelValueCommand` 無法將 Python 代碼正確顯示在節點 UI 中，即使模型屬性已更新。

---

## 解決方案：三重保障機制

### 1. 名稱循環嘗試 (Node Creation Name Loop)

依序嘗試多個可能的節點名稱，確保跨版本相容性：

```csharp
string[] possibleNames = { 
    "Python Script",                  // 3.3+ 推薦
    "Core.Scripting.Python Script",   // 3.0-3.2
    "PythonScript"                    // 2.x
};
```

### 2. 專用指令反射調用 (Dedicated Command Reflection)

動態搜尋並調用 Dynamo 內部的 `UpdatePythonNodeCommand`：

```csharp
// 在所有已載入組件中搜尋專用指令
Type cmdType = asm.GetType("Dynamo.Models.DynamoModel+UpdatePythonNodeCommand");
object cmdInstance = Activator.CreateInstance(cmdType, new object[] { 
    dynamoGuid, pythonCode, "CPython3" 
});
_model.ExecuteCommand(cmdInstance as RecordableCommand);
```

**優勢**：同時設置代碼與 CPython3 引擎，符合 Dynamo 內部設計邏輯。

### 3. UI 強制同步 (Forced UI Sync)

反射調用 `OnNodeModified` 方法，強制 WPF UI 重新讀取屬性：

```csharp
// 直接設置 Script 屬性
PropertyInfo scriptProp = pythonNode.GetType()
    .GetProperty("Script", BindingFlags.Public | BindingFlags.Instance);
scriptProp.SetValue(pythonNode, pythonCode);

// 觸發 UI 更新通知
MethodInfo onModified = pythonNode.GetType()
    .GetMethod("OnNodeModified", BindingFlags.NonPublic | BindingFlags.Instance);
onModified.Invoke(pythonNode, new object[] { true });
```

---

## 成功率

**100%** - 已驗證可正確顯示代碼與設置 CPython3 引擎

---

## 參考文件

- 📘 詳細技術說明：[`domain/python_script_automation.md`](../../domain/python_script_automation.md)
- 📘 English Version: [`domain/python_script_automation_EN.md`](../../domain/python_script_automation_EN.md)
- 🔧 C# 實作：`DynamoViewExtension/src/GraphHandler.cs:L314-363`
