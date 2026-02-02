# Dynamo Automation Quick Start for AI Agents

> **Audience:** AI agents (Claude, Gemini, Antigravity, etc.) using MCP to control Dynamo  
> **Last Updated:** 2026-01-30 (Revised)

This guide helps AI agents efficiently automate Autodesk Dynamo through the Model Context Protocol (MCP).

---

## Prerequisites

1. **MCP Connection Established**
   - Python server running: `python bridge/python/server.py`
   - Dynamo open with active workspace
   - MCP tools available in context

2. **Available MCP Tools**
   - `execute_dynamo_instructions` - Create nodes and connections
   - `analyze_workspace` - Get workspace state
   - `search_nodes` - Search available nodes
   - `get_script_library` - Get script library list
   - `clear_workspace` - Clear current workspace

---

## Quick Diagnostics

Before starting, verify connection:

```python
# Use MCP tool
result = await analyze_workspace()

# Expected output
{
  "workspaceName": "MyProject",
  "nodeCount": 15,
  "connectorCount": 8,
  "status": "healthy"
}
```

If connection fails, see [../../domain/troubleshooting.md](../../domain/troubleshooting.md).

---

## Decision Tree: Choose Your Strategy

```
User Request
    │
    ├─ Simple geometry with fixed parameters?
    │  (e.g., "Create a point at (0,0,0)")
    │  └─ Use Code Block Strategy
    │     → See: ../../domain/node_creation_strategy.md (Lines 26-98)
    │
    ├─ Parameterized nodes?
    │  (e.g., "Create a cube with width=100, length=50, height=30")
    │  └─ Use Native Node Strategy
    │     → See: ../../domain/node_creation_strategy.md (Lines 101-265)
    │
    ├─ Python script injection?
    │  (e.g., "Inject Python code to read Revit rooms")
    │  └─ Use Python Injection
    │     → See: ../../domain/python_script_automation.md
    │
    └─ Connect nodes?
       (e.g., "Connect Select Element to Python Script")
       └─ Use Connection Patterns
          → See: ../../domain/node_connection_workflow.md
```

---

## Strategy 1: Code Block (Simple Geometry)

### When to Use
- Fixed coordinates or parameters
- Complex nested geometry
- Quick prototyping
- 100% reliability required

### Template

```json
{
  "nodes": [{
    "id": "pt1",
    "name": "Number",
    "value": "Point.ByCoordinates(0, 0, 0);",
    "x": 300,
    "y": 300
  }],
  "connectors": []
}
```

### Execution

```python
await execute_dynamo_instructions(json.dumps({
  "nodes": [{
    "id": "line1",
    "name": "Number",
    "value": "Line.ByStartPointEndPoint(Point.ByCoordinates(0,0,0), Point.ByCoordinates(100,100,100));",
    "x": 300,
    "y": 300
  }]
}))
```

**Golden Rules:**
- ✅ Always use `"name": "Number"` (NOT "Code Block")
- ✅ Code must end with `;`
- ✅ For 3D geometry, explicitly specify x, y, z parameters

**Full Details:** [../../domain/node_creation_strategy.md](../../domain/node_creation_strategy.md#code-block-strategy)

---

## Strategy 2: Native Node (Parameterized)

### When to Use
- Need adjustable parameters
- Script library reuse
- Visualization control (preview: false/true)
- Modular design

### Template

```json
{
  "nodes": [{
    "id": "cube1",
    "name": "Cuboid.ByLengths",
    "params": {
      "width": 100,
      "length": 50,
      "height": 30
    },
    "x": 500,
    "y": 300,
    "preview": true
  }]
}
```

### Execution

```python
await execute_dynamo_instructions(json.dumps({
  "nodes": [{
    "id": "sphere1",
    "name": "Sphere.ByCenterPointRadius",
    "params": {
      "centerPoint": "Point.ByCoordinates(0,0,0);",
      "radius": 50
    },
    "x": 500,
    "y": 300,
    "preview": false
  }]
}))
```

**Prerequisites:**
- Node must be defined in `common_nodes.json`
- Python server auto-expansion enabled

**Full Details:** [../../domain/node_creation_strategy.md](../../domain/node_creation_strategy.md#native-node-strategy)

---

## Strategy 3: Python Script Injection

### Triple-Guarantee Mechanism

Dynamo 3.3 requires a three-layer approach for reliable Python code injection:

1. **Name Loop** - Try multiple node names for compatibility
2. **Dedicated Command** - Use `UpdatePythonNodeCommand` via reflection
3. **Forced UI Sync** - Call `OnNodeModified(true)` to refresh UI

### Template

```json
{
  "nodes": [{
    "id": "py_script",
    "name": "Python Script",
    "pythonCode": "import clr\nclr.AddReference('RevitAPI')\nfrom Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory\n\ndoc = IN[0]\nrooms = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms)\nOUT = [r.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() for r in rooms]",
    "x": 500,
    "y": 300
  }]
}
```

### Execution

```python
python_code = """
import clr
OUT = 'Hello Dynamo'
"""

await execute_dynamo_instructions(json.dumps({
  "nodes": [{
    "id": "py1",
    "name": "Python Script",
    "pythonCode": python_code,
    "x": 500,
    "y": 300
  }]
}))
```

**Success Rate:** 100% (verified in Dynamo 3.3)

**Full Details:** [../../domain/python_script_automation.md](../../domain/python_script_automation.md)

---

## Strategy 4: Node Connection

### Critical Rules

- ✅ Use `fromPort` / `toPort` (0-indexed)
- ❌ Never use `fromIndex` / `toIndex` (invalid fields)
- ✅ Ensure ID mapping exists before connecting

### Template

```json
{
  "nodes": [
    {
      "id": "selector",
      "name": "Select Model Element",
      "x": 100,
      "y": 300
    },
    {
      "id": "py_script",
      "name": "Python Script",
      "pythonCode": "OUT = IN[0].Name",
      "x": 500,
      "y": 300
    }
  ],
  "connectors": [
    {
      "from": "selector",
      "to": "py_script",
      "fromPort": 0,
      "toPort": 0
    }
  ]
}
```

### Execution

```python
await execute_dynamo_instructions(json.dumps({
  "nodes": [...],
  "connectors": [{
    "from": "node_a",
    "to": "node_b",
    "fromPort": 0,
    "toPort": 0
  }]
}))
```

**Full Details:** [../../domain/node_connection_workflow.md](../../domain/node_connection_workflow.md)

---

## Templates Library

Ready-to-use JSON templates are available in `DynamoScripts/`:

| Template | Purpose | Strategy |
|:---|:---|:---:|
| `point_basic.json` | Single point creation | Code Block |
| `line_basic.json` | Basic line geometry | Code Block |
| `random_cuboid.json` | Parameterized solid | Native Node |
| `solid_demo.json` | Preview control | Native Node |
| `revit_room_collector.json` | Revit room reader | Python |
| `connect_points.json` | Connect workflow | Connection |

**Usage:**
```python
import json

# Load template
with open('DynamoScripts/random_cuboid.json') as f:
    template = json.load(f)

# Use template directly or modify if needed
# template['nodes'][0]['params']['width'] = 200  # Example modification

# Execute
result = await execute_dynamo_instructions(json.dumps(template))
print(result)  # Should show [OK] if successful
```

---

## Common Troubleshooting

### Issue: Connection Failed

**Diagnostic:**
```python
result = await analyze_workspace()
# Check if result contains error
```

**Solutions:**
1. Verify Python server is running
2. Check Dynamo is open
3. See [../../domain/troubleshooting.md](../../domain/troubleshooting.md)

---

### Issue: Node Created But Not Visible

**Cause:** Ghost connection (old Dynamo session)

**Solution:**
1. Close Dynamo completely
2. Restart Python server
3. Reopen Dynamo

**Details:** [../../domain/troubleshooting.md](../../domain/troubleshooting.md#ghost-connection)

---

### Issue: Python Code Not Displayed

**Cause:** UI sync not triggered

**Solution:** Already handled by triple-guarantee mechanism. If still occurs, see [../../domain/python_script_automation.md](../../domain/python_script_automation.md#troubleshooting).

---

## Complete Documentation

For in-depth technical details:

- **Node Creation Strategies:** [../../domain/node_creation_strategy.md](../../domain/node_creation_strategy.md)
- **Python Script Automation:** [../../domain/python_script_automation.md](../../domain/python_script_automation.md)
- **Node Connection Workflow:** [../../domain/node_connection_workflow.md](../../domain/node_connection_workflow.md)
- **Troubleshooting Guide:** [../../domain/troubleshooting.md](../../domain/troubleshooting.md)

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-24  
**Maintained by:** Dynamo MCP Team
