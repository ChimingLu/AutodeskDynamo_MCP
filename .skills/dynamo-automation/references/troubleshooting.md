# Troubleshooting Guide

> **Source:** `../../domain/troubleshooting.md` + Core Lessons from `GEMINI.md`  
> **Last Updated:** 2026-01-24

This reference provides solutions to common issues when working with Dynamo MCP automation.

## Connection Issues

### Issue: MCP Server Not Responding

**Symptoms:**
- Tool calls timeout
- No response from Dynamo

**Diagnostic:**
```bash
# Check if Python server is running
python .skills/dynamo-automation/scripts/check_connection.py
```

**Solutions:**
1. Restart Python server: `python bridge/python/server.py`
2. Verify Dynamo is open
3. Check WebSocket port 65535 is not blocked

---

### Issue: Ghost Connection

**Definition:**
Revit not closed but Dynamo window was reopened, causing AI commands to succeed but user sees no results.

**Diagnostic Criteria:**
```
IF analyze_workspace.nodeCount > 1 
   AND user reports "cannot see nodes"
THEN Ghost connection detected
```

**Solution:**
1. Stop MCP server
2. Restart Dynamo to clear residual state
3. Reconnect

**Prevention:**
Execute `analyze_workspace` at conversation start and report:
- Workspace Name
- Node Count
- Session State (SessionId changes)

---

## Node Creation Issues

### Issue: Node Created But Not Visible

**Symptoms:**
- Python shows ✅ success
- C# side properties updated
- ❌ Dynamo UI shows nothing

**Cause:** UI thread not wrapped (violates Core Lesson #9)

**Solution:**
```csharp
// Ensure operations execute on UI thread
await System.Windows.Application.Current.Dispatcher.InvokeAsync(() => 
{
    _handler.HandleCommand(json);
});
```

---

### Issue: Z Coordinate Ignored

**Symptoms:**
Point created at 2D instead of 3D

**Cause:**
Used 2D version of `Point.ByCoordinates`

**Solution:**
Explicitly specify 3 parameters:
```json
{
  "value": "Point.ByCoordinates(x, y, z);"
}
```

Or add overload specification (Native Node strategy):
```json
{
  "name": "Point.ByCoordinates",
  "overload": "3D",
  "params": {"x": 0, "y": 0, "z": 0}
}
```

---

## Python Script Issues

### Issue: Code Not Displayed in Node

**Symptoms:**
- Python Script node created
- Node is blank in UI

**Possible Causes:**
1. Dedicated command failed
2. UI sync not triggered
3. Incorrect property name

**Solution:**
Ensure triple-guarantee mechanism is applied:
1. Name Loop (try multiple node names)
2. Dedicated Command (`UpdatePythonNodeCommand`)
3. Forced UI Sync (`OnNodeModified(true)`)

See: [python_injection.md](python_injection.md)

---

### Issue: Engine Still IronPython2

**Symptoms:**
Node shows IronPython2 instead of CPython3

**Solution:**
Explicitly set EngineName property:
```csharp
PropertyInfo engineProp = createdNode.GetType()
    .GetProperty("EngineName", BindingFlags.Public | BindingFlags.Instance);
if (engineProp != null && engineProp.CanWrite) {
    engineProp.SetValue(createdNode, "CPython3");
}
```

---

## Connection Issues

### Issue: Zombie Nodes (No Connections)

**Symptoms:**
- Nodes exist on canvas
- Connections not established

**Cause:**
ID mapping not recorded before connection

**Solution:**
Ensure node creation completes before connecting:
```python
# Create all nodes first
for node in instruction['nodes']:
    await create_node(node)

# Then create connections
for conn in instruction['connectors']:
    await create_connection(conn)
```

---

### Issue: Port Index Out of Range

**Cause:**
Incorrect port index in JSON

**Solution:**
1. Check `common_nodes.json` for correct port order
2. Verify `fromPort`/`toPort` values (0-indexed)
3. Ensure using `fromPort`/`toPort` (not `fromIndex`/`toIndex`)

---

## Workflow Issues

### Issue: Repeated Code Generation

**Symptom:**
AI regenerates same JSON instead of reusing library scripts

**Solution:**
Check script library first:
```python
# Query library
scripts = await get_script_library()

# If exists, load it
if "basic_house" in scripts:
    json_content = await load_script_from_library("basic_house")
else:
    # Generate new JSON
    json_content = generate_new_json()
```

---

## Emergency Recovery

### Complete Reset Procedure

When all else fails:

1. **Stop all services:**
   ```bash
   # Kill Python server
   # Close Dynamo
   # Close Revit
   ```

2. **Clear logs:**
   ```powershell
   Remove-Item $env:AppData\Dynamo\MCP\DynamoMCP.log
   ```

3. **Restart in order:**
   ```bash
   # 1. Start Python server
   python bridge/python/server.py
   
   # 2. Open Revit
   # 3. Open Dynamo
   # 4. Reconnect MCP
   ```

4. **Verify connection:**
   ```bash
   python .skills/dynamo-automation/scripts/check_connection.py
   ```

---

## Complete Documentation

For full troubleshooting details and additional diagnostics, see:

📘 **[Troubleshooting SOP](../../domain/troubleshooting.md)**  
📘 **[GEMINI.md Core Lessons](../../GEMINI.md)**
