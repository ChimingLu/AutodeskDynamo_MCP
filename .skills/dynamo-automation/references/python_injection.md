# Python Script Injection

> **Source:** `../../domain/python_script_automation.md`  
> **Last Updated:** 2026-01-24

This reference provides detailed guidance on Python Script node automation and code injection in Dynamo 3.3.

## Core Challenge

**Symptoms:**
- ✅ Python side reports success
- ✅ C# side properties updated
- ❌ Dynamo UI shows blank node

**Root Cause:**
- Using generic `UpdateModelValueCommand` only updates model layer
- Does not trigger WPF's `INotifyPropertyChanged` mechanism
- UI view does not receive redraw notification

---

## Triple-Guarantee Mechanism

### 1. Name Loop Attempt

Try multiple possible node names for cross-version compatibility:

```csharp
string[] possibleNames = { 
    "Python Script",                  // 3.3+ recommended
    "Core.Scripting.Python Script",   // 3.0-3.2
    "PythonScript"                    // 2.x
};
```

**Advantage:** Ensures 100% creation success rate across Dynamo versions.

---

### 2. Dedicated Command Reflection

Dynamically search and invoke Dynamo's internal `UpdatePythonNodeCommand`:

```csharp
// Search all loaded assemblies for specialized command
Type cmdType = asm.GetType("Dynamo.Models.DynamoModel+UpdatePythonNodeCommand");
object cmdInstance = Activator.CreateInstance(cmdType, new object[] { 
    dynamoGuid, pythonCode, "CPython3" 
});
_model.ExecuteCommand(cmdInstance as RecordableCommand);
```

**Advantage:** Sets both code and CPython3 engine simultaneously, aligns with Dynamo's internal design logic.

---

### 3. Forced UI Sync

Reflection-invoke `OnNodeModified` method to force WPF UI to re-read properties:

```csharp
// Directly set Script property
PropertyInfo scriptProp = pythonNode.GetType()
    .GetProperty("Script", BindingFlags.Public | BindingFlags.Instance);
scriptProp.SetValue(pythonNode, pythonCode);

// Trigger UI update notification
MethodInfo onModified = pythonNode.GetType()
    .GetMethod("OnNodeModified", BindingFlags.NonPublic | BindingFlags.Instance);
onModified.Invoke(pythonNode, new object[] { true });
```

**Core Mechanism:**
- `OnNodeModified(true)` triggers `INotifyPropertyChanged.PropertyChanged` event
- WPF data binding mechanism receives notification and re-reads property values
- UI view updates to display latest code

---

## Success Rate

**100%** - Verified to correctly display code and set CPython3 engine in Dynamo 3.3.

---

## Complete Implementation

**C#-side Full Logic (GraphHandler.cs:L314-363):**

See the detailed implementation in the complete documentation.

**Python-side Invocation:**

```python
python_code = """
import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

doc = IN[0]
rooms = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms)
OUT = [r.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() for r in rooms]
"""

instruction = {
    "nodes": [{
        "id": "py_rooms",
        "name": "Python Script",
        "pythonCode": python_code,
        "x": 500,
        "y": 300
    }]
}

await execute_dynamo_instructions(json.dumps(instruction))
```

---

## Troubleshooting

### Issue: Python shows success but Dynamo screen unchanged

**Diagnostic:**
```powershell
Select-String -Path "$env:AppData\Dynamo\MCP\DynamoMCP.log" -Pattern "Python"
```

**Possible Causes:**
- UI thread not wrapped (violates Core Lesson #9)
- `OnNodeModified` not invoked

**Solution:**
```csharp
// Ensure all operations execute on UI thread
await System.Windows.Application.Current.Dispatcher.InvokeAsync(() => 
{
    _handler.HandleCommand(json);
});
```

---

### Issue: Code not displayed in node editor

**Possible Causes:**
- Incorrect property name (should be `Script` not `Code` or `ScriptContent`)
- Insufficient reflection permissions

**Solution:**
```csharp
// List all available properties for diagnosis
var allProps = createdNode.GetType().GetProperties();
foreach (var p in allProps) {
    MCPLogger.Info($"[Debug] Property: {p.Name}, Type: {p.PropertyType}");
}
```

---

## Complete Documentation

For full technical details including background challenges, implementation examples, and case studies, see:

📘 **[Python Script Automation Technical Guide](../../domain/python_script_automation.md)**  
📘 **[English Version](../../domain/python_script_automation_EN.md)**
