# Node Connection Patterns

> **Source:** `../../domain/node_connection_workflow.md`  
> **Last Updated:** 2026-01-24

This reference provides detailed guidance on automated node connections and cross-language ID mapping.

## Connection Mechanism

### Dynamo Native Connection System

Dynamo uses `MakeConnectionCommand` to establish connections:

```csharp
public class MakeConnectionCommand : RecordableCommand
{
    public Guid NodeId { get; }        // Source node GUID
    public int PortIndex { get; }      // Source port index
    public Guid OtherNodeId { get; }   // Target node GUID
    public int OtherPortIndex { get; } // Target port index
}
```

### Port Index Rules

| Property | Description | Index Rules |
|:---|:---|:---|
| **Input Ports** | Left side of node, receives data | Top to bottom: 0, 1, 2, ... |
| **Output Ports** | Right side of node, outputs data | Top to bottom: 0, 1, 2, ... |

**Important:** Most nodes have only **1 output port** (index 0), but may have multiple input ports.

---

## Cross-Language ID Mapping

### Design Challenge

| Layer | ID Type | Example | Purpose |
|:---|:---|:---|:---|
| **Python Side** | String | `"pt1"`, `"cube_width_1234"` | Human-readable, easy to parameterize |
| **C# Side** | GUID | `3fa85f64-5717-4562-b3fc-2c963f66afa6` | Dynamo internal identifier |

### Solution: Bidirectional Mapping Table

**Node Creation Recording (GraphHandler.cs:L120-127):**
```csharp
Guid dynamoGuid = Guid.TryParse(nodeIdStr, out Guid parsedGuid) 
    ? parsedGuid : Guid.NewGuid();
_nodeIdMap[nodeIdStr] = dynamoGuid;  // Record "pt1" -> GUID
```

**Connection Query (GraphHandler.cs:L244-256):**
```csharp
if (!_nodeIdMap.TryGetValue(fromIdStr, out fromId)) {
    fromId = Guid.Parse(fromIdStr);  // Fallback
}
```

---

## JSON Connection Format

### Standard Format

```json
{
  "connectors": [
    {
      "from": "source_node_id",
      "to": "target_node_id",
      "fromPort": 0,
      "toPort": 0
    }
  ]
}
```

### Field Specifications

| Field | Type | Required | Description |
|:---|:---|:---:|:---|
| `from` | String | ✅ | Python string ID of source node |
| `to` | String | ✅ | Python string ID of target node |
| `fromPort` | Integer | ✅ | Source node output port index (0-indexed) |
| `toPort` | Integer | ✅ | Target node input port index (0-indexed) |

**⚠️ Critical:**
- **Must use `fromPort` and `toPort`** (not `fromIndex` or `toIndex`)
- Port indices start from **0**
- Output ports typically only have index 0

---

## Real-World Case

### Case: Select Model Element → Python Script

**Goal:** Automatically connect Revit element selector to Python analysis script.

**JSON Command:**
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

**Execution Results:**
- ✅ Two nodes successfully created
- ✅ Connection correctly established
- ✅ Python node can receive selector output

---

## Troubleshooting

### Issue: Zombie Nodes (Nodes Without Connections)

**Symptoms:**
- Nodes created on canvas
- Connections not established
- No error messages in logs

**Possible Causes:**
1. Python string ID not recorded in `_nodeIdMap`
2. Connection command executed before mapping recorded (sequencing issue)

**Solution:**
```csharp
// Ensure all nodes created before executing connections
foreach (JToken n in nodes) {
    CreateNode(n);  // Create all nodes first
}

foreach (JToken c in connectors) {
    CreateConnection(c);  // Then create all connections
}
```

---

### Issue: Incorrect Port Index

**Symptoms:**
- Connection established but connects to wrong port
- Dynamo shows "Port index out of range" error

**Solution:**
Verify port definition in `common_nodes.json`:
```json
{
  "Cuboid.ByLengths": {
    "inputs": ["width", "length", "height"],  // Order: 0, 1, 2
  }
}
```

---

### Issue: Incorrect Connection Field Names

**Cause:** Using `fromIndex`/`toIndex` instead of `fromPort`/`toPort`.

**Solution:**
```json
// ❌ Wrong
{"from": "a", "to": "b", "fromIndex": 0, "toIndex": 1}

// ✅ Correct
{"from": "a", "to": "b", "fromPort": 0, "toPort": 1}
```

---

## Complete Documentation

For full technical details including auto-connection generation, preview control, and sequence diagrams, see:

📘 **[Node Connection Workflow Guide](../../domain/node_connection_workflow.md)**  
📘 **[English Version](../../domain/node_connection_workflow_EN.md)**
