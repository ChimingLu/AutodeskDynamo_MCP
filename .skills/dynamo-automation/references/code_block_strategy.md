# Code Block Strategy (Track A)

> **Source:** `../../domain/node_creation_strategy.md` (Lines 26-98)  
> **Last Updated:** 2026-01-24

This reference provides detailed guidance on using the Code Block approach for Dynamo node creation.

## When to Use

| Scenario | Reason |
|:---|:---|
| Simple single geometry | Fixed parameters, no adjustment needed |
| Complex nested geometry | API limitation, cannot create separately |
| Quick prototyping | Shortest path, no metadata configuration |
| Fallback strategy | When Track B (Native Node) connection fails |

---

## Golden Rules

| Rule | Description | Example |
|:---|:---|:---|
| **Node Name** | Always use `"Number"` | ❌ `"Code Block"` ✅ `"Number"` |
| **Code Field** | Write complete DesignScript in `value` | `"value": "Point.ByCoordinates(0,0,0);"` |
| **Syntax Terminator** | All code must end with `;` | ❌ `"(0,0,0)"` ✅ `"(0,0,0);"` |
| **Conversion Mechanism** | `GraphHandler.cs` auto-converts `"Number"` to Code Block | No manual node type specification needed |

---

## Implementation Examples

### Example 1: Simple Point

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

### Example 2: Complex Boolean Operation

```json
{
  "nodes": [{
    "id": "result1",
    "name": "Number",
    "value": "Solid.Difference(Cuboid.ByLengths(100,50,30), Sphere.ByCenterPointRadius(Point.ByCoordinates(50,25,15), 20));",
    "x": 500,
    "y": 300
  }],
  "connectors": []
}
```

### Example 3: Multi-layer Nested Geometry

```json
{
  "nodes": [{
    "id": "complex1",
    "name": "Number",
    "value": "Line.ByStartPointEndPoint(Point.ByCoordinates(0,0,0), Point.ByCoordinates(100,100,100));",
    "x": 300,
    "y": 300
  }],
  "connectors": []
}
```

---

## Advantages & Limitations

| Advantages ✅ | Limitations ❌ |
|:---|:---|
| 100% reliable, no connection failure risk | JSON readability poor (logic squeezed in strings) |
| Suitable for complex nested geometry | Difficult to parameterize (can't easily extract `width`, `height`) |
| Aligns with Dynamo's native design philosophy | Higher AI token consumption (long strings) |
| No need to configure `common_nodes.json` | Cannot utilize `base_x`, `base_y` offset features |

---

## Complete Documentation

For full technical details including decision matrices, troubleshooting, and advanced patterns, see:

📘 **[Node Creation Strategy Guide](../../domain/node_creation_strategy.md)**
