---
name: dynamo-automation
description: Specialized workflow for automating Autodesk Dynamo graph creation through MCP. Use when the user requests (1) Creating or placing Dynamo nodes (native/packages/custom), (2) Injecting Python scripts into Dynamo nodes, (3) Establishing node connections, (4) Analyzing workspace state, (5) Troubleshooting MCP integration (ghost connections, UI sync issues), (6) Working with Dynamo script libraries.
---

# Dynamo Automation Skill

> **Note for All AI Agents:**  
> This is the Antigravity-specific Skill wrapper with auto-triggering capability.  
> **Universal Documentation:** See [`../../docs/ai-guide/quick-start.md`](../../docs/ai-guide/quick-start.md) for complete guidance.

---

Fast-track workflow for controlling Autodesk Dynamo through Model Context Protocol (MCP).

## For Non-Antigravity Users

If you're using Claude Desktop, Gemini CLI, or other AI agents:
- This Skill will not auto-trigger
- Please refer to **[docs/ai-guide/quick-start.md](../../docs/ai-guide/quick-start.md)** directly
- All MCP tools work the same across all AI agents

---

## Quick Start

### 1. Environment Check

```bash
python .skills/dynamo-automation/scripts/check_connection.py
```

If connection fails → See [Troubleshooting](references/troubleshooting.md)

### 2. Choose Your Strategy

**Decision Tree:**

```
User Request
    ├─ Simple geometry with fixed params?
    │  └─ Use Code Block Strategy → references/code_block_strategy.md
    │
    ├─ Parameterized nodes?
    │  └─ Use Native Node Strategy → references/native_node_strategy.md
    │
    ├─ Python script injection?
    │  └─ Use Python Injection → references/python_injection.md
    │
    └─ Connect nodes?
       └─ Use Connection Patterns → references/connection_patterns.md
```

---

## Core Workflows

### Node Creation

**Strategy Selection:**

| Scenario | Strategy | Reference |
|:---|:---:|:---|
| Fixed coordinates (e.g., `Point(0,0,0)`) | Code Block | [code_block_strategy.md](references/code_block_strategy.md) |
| Parameterized (e.g., `Cuboid(width, length, height)`) | Native Node | [native_node_strategy.md](references/native_node_strategy.md) |
| Complex nested geometry | Code Block | [code_block_strategy.md](references/code_block_strategy.md) |

**Quick Templates:**
- See `assets/templates/` for ready-to-use JSON examples

---

### Python Script Injection

**Triple-Guarantee Mechanism:**

1. **Name Loop** - Try multiple node names for cross-version compatibility
2. **Dedicated Command** - Use `UpdatePythonNodeCommand` via reflection
3. **Forced UI Sync** - Call `OnNodeModified(true)` to refresh UI

**Full details:** [python_injection.md](references/python_injection.md)

**Quick Template:**
```json
{
  "nodes": [{
    "id": "py_script",
    "name": "Python Script",
    "pythonCode": "OUT = IN[0]",
    "x": 500,
    "y": 300
  }]
}
```

---

### Node Connection

**Critical Rules:**

- ✅ Use `fromPort` / `toPort` (0-indexed)
- ❌ Never use `fromIndex` / `toIndex` (invalid fields)
- ✅ Ensure ID mapping exists before connecting

**Full details:** [connection_patterns.md](references/connection_patterns.md)

**Quick Template:**
```json
{
  "connectors": [{
    "from": "node_a",
    "to": "node_b",
    "fromPort": 0,
    "toPort": 0
  }]
}
```

---

## Workspace Analysis

**Analyze current state:**

```bash
python .skills/dynamo-automation/scripts/analyze_workspace.py
```

**Returns:**
- Workspace name & file path
- Node count & types
- Connection status
- Error/warning flags

---

## Templates Library

**Location:** `assets/templates/`

| Template | Purpose | Strategy |
|:---|:---|:---:|
| `point_basic.json` | Single point creation | Code Block |
| `line_nested.json` | Nested geometry example | Code Block |
| `cuboid_parameterized.json` | Parameterized solid | Native Node |
| `sphere_with_preview.json` | Preview control demo | Native Node |
| `python_basic.json` | Empty Python node | Python |
| `python_revit_rooms.json` | Revit room reader | Python |
| `connection_workflow.json` | Select → Python workflow | Connection |

**Usage:**
```python
# Load template
import json
with open('.skills/dynamo-automation/assets/templates/point_basic.json') as f:
    template = json.load(f)

# Modify coordinates
template['nodes'][0]['value'] = "Point.ByCoordinates(100, 200, 300);"

# Execute
await execute_dynamo_instructions(json.dumps(template))
```

---

## Common Patterns

### Pattern 1: Code Block (Simple Geometry)

```json
{
  "nodes": [{
    "id": "geom1",
    "name": "Number",
    "value": "Point.ByCoordinates(0, 0, 0);",
    "x": 300,
    "y": 300
  }]
}
```

### Pattern 2: Native Node (Parameterized)

```json
{
  "nodes": [{
    "id": "cube1",
    "name": "Cuboid.ByLengths",
    "params": {"width": 100, "length": 50, "height": 30},
    "x": 500,
    "y": 300
  }]
}
```

### Pattern 3: Python Script

```json
{
  "nodes": [{
    "id": "py1",
    "name": "Python Script",
    "pythonCode": "import clr\nOUT = 'Hello Dynamo'",
    "x": 500,
    "y": 300
  }]
}
```

---

## Troubleshooting

### Issue: Connection failed

**Check:**
1. Is Python WebSocket server running? (`python bridge/python/server.py`)
2. Is Dynamo open with workspace active?
3. Run `scripts/check_connection.py` for diagnostics

**Solutions:** See [troubleshooting.md](references/troubleshooting.md)

---

### Issue: Node created but not visible

**Cause:** Ghost connection (old Dynamo session)

**Solution:**
1. Close Dynamo completely
2. Restart Python server
3. Reopen Dynamo
4. Reconnect

**Details:** [troubleshooting.md](references/troubleshooting.md#ghost-connection)

---

## References

All detailed technical documentation is in `references/`:

- [code_block_strategy.md](references/code_block_strategy.md) - Code Block approach (Track A)
- [native_node_strategy.md](references/native_node_strategy.md) - Native Node approach (Track B)
- [python_injection.md](references/python_injection.md) - Python Script automation
- [connection_patterns.md](references/connection_patterns.md) - Node connection mechanics
- [troubleshooting.md](references/troubleshooting.md) - Common issues & solutions

---

**Skill Version:** 1.0  
**Last Updated:** 2026-01-24  
**Maintained by:** Dynamo MCP Team
