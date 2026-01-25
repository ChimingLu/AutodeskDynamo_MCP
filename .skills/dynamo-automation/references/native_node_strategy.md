# Native Node Strategy (Track B)

> **Source:** `../../domain/node_creation_strategy.md` (Lines 101-265)  
> **Last Updated:** 2026-01-24

This reference provides detailed guidance on using the Native Node Auto-Expansion approach for Dynamo node creation.

## When to Use

| Scenario | Example | Reason |
|:---|:---|:---|
| Parameterized nodes | `Cuboid.ByLengths(width, length, height)` | Need adjustable parameters |
| Script library reuse | Load saved scripts with offset | Support `base_x`, `base_y` parameters |
| Visualization control | Hide intermediate geometry | Can set `preview: false` |
| Modular design | Independent parameterized components | Easy to reuse and adjust |

---

## Prerequisites

| Check Item | Verification Method | Failure Handling |
|:---|:---|:---|
| ✅ Node defined in `common_nodes.json` | Search node name | Fallback to Track A |
| ✅ Port order correctly configured | Check `inputs` array | Manually fix metadata |
| ✅ `server.py` auto-expansion enabled | Check Lines 414-470 | Ensure code not commented |

---

## Technical Principles

### Python-side Auto-Expansion Logic

**Process:**
1. Detect `_strategy` in node JSON (`"NATIVE_DIRECT"` or `"NATIVE_WITH_OVERLOAD"`)
2. Get correct port order from `common_nodes.json`
3. Create Number node for each parameter
4. Auto-generate connectors

**Example expansion:**

**Input:**
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

**Auto-expanded:**
```json
{
  "nodes": [
    {"id": "cube1", "name": "Cuboid.ByLengths", "x": 500, "y": 300},
    {"id": "cube1_width_1706083200000", "name": "Number", "value": "100", "x": 300, "y": 300},
    {"id": "cube1_length_1706083200000", "name": "Number", "value": "50", "x": 300, "y": 380},
    {"id": "cube1_height_1706083200000", "name": "Number", "value": "30", "x": 300, "y": 460}
  ],
  "connectors": [
    {"from": "cube1_width_1706083200000", "to": "cube1", "fromPort": 0, "toPort": 0},
    {"from": "cube1_length_1706083200000", "to": "cube1", "fromPort": 0, "toPort": 1},
    {"from": "cube1_height_1706083200000", "to": "cube1", "fromPort": 0, "toPort": 2}
  ]
}
```

---

### C#-side ID Mapping Mechanism

**Node Creation Recording:**
```csharp
Guid dynamoGuid = Guid.NewGuid();
_nodeIdMap[nodeIdStr] = dynamoGuid; // Record "cube1" -> GUID
```

**Connection Query:**
```csharp
if (!_nodeIdMap.TryGetValue(fromIdStr, out fromId)) {
    fromId = Guid.Parse(fromIdStr); // Fallback: direct parse
}
```

---

## Implementation Examples

### Example 1: Parameterized Cuboid

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
    "preview": false
  }],
  "connectors": []
}
```

### Example 2: Point with Overload

```json
{
  "nodes": [{
    "id": "pt1",
    "name": "Point.ByCoordinates",
    "params": {
      "x": 100,
      "y": 200,
      "z": 300
    },
    "overload": "3D",
    "x": 500,
    "y": 300
  }],
  "connectors": []
}
```

### Example 3: Hidden Intermediate Node

```json
{
  "nodes": [{
    "id": "sphere1",
    "name": "Sphere.ByCenterPointRadius",
    "params": {
      "centerPoint": "Point.ByCoordinates(0,0,0);",
      "radius": 50
    },
    "x": 500,
    "y": 300,
    "preview": false,
    "_comment": "Intermediate sphere, hidden for boolean operation"
  }]
}
```

---

## Advantages & Limitations

| Advantages ✅ | Limitations ❌ |
|:---|:---|
| JSON structure clear, strong semantics | Depends on cross-language ID mapping, high technical complexity |
| Easy to parameterize and reuse | Connection failure creates "zombie nodes" |
| Auto-inherits `preview` property | Requires maintaining `common_nodes.json` port definitions |
| Supports `base_x`, `base_y` offset | Cannot handle complex nested geometry (will be flattened) |

---

## Complete Documentation

For full technical details including auto-expansion logic, ID mapping, and troubleshooting, see:

📘 **[Node Creation Strategy Guide](../../domain/node_creation_strategy.md)**
