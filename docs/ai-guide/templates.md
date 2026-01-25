# Templates Reference for AI Agents

> **Audience:** AI agents using MCP to control Dynamo  
> **Last Updated:** 2026-01-24

This document provides a comprehensive reference for all available JSON templates.

---

## Template Locations

All templates are stored in:
```
.skills/dynamo-automation/assets/templates/
```

---

## Code Block Templates

### 1. point_basic.json

**Purpose:** Create a single point at origin  
**Strategy:** Code Block  
**Use Case:** Simple geometry, fixed coordinates

```json
{
  "nodes": [{
    "id": "pt_basic",
    "name": "Number",
    "value": "Point.ByCoordinates(0, 0, 0);",
    "x": 300,
    "y": 300
  }],
  "connectors": []
}
```

**Modification Example:**
```python
template['nodes'][0]['value'] = "Point.ByCoordinates(100, 200, 300);"
```

---

### 2. line_nested.json

**Purpose:** Create a line with nested point creation  
**Strategy:** Code Block  
**Use Case:** Demonstrates complex nested geometry

```json
{
  "nodes": [{
    "id": "line_nested",
    "name": "Number",
    "value": "Line.ByStartPointEndPoint(Point.ByCoordinates(0,0,0), Point.ByCoordinates(100,100,100));",
    "x": 300,
    "y": 300
  }],
  "connectors": []
}
```

**Modification Example:**
```python
# Change endpoint
template['nodes'][0]['value'] = "Line.ByStartPointEndPoint(Point.ByCoordinates(0,0,0), Point.ByCoordinates(200,200,200));"
```

---

## Native Node Templates

### 3. cuboid_parameterized.json

**Purpose:** Create a parameterized cuboid  
**Strategy:** Native Node with auto-expansion  
**Use Case:** Adjustable parameters, modular design

```json
{
  "nodes": [{
    "id": "cuboid_param",
    "name": "Cuboid.ByLengths",
    "params": {
      "width": 100,
      "length": 50,
      "height": 30
    },
    "x": 500,
    "y": 300,
    "preview": true
  }],
  "connectors": []
}
```

**Modification Example:**
```python
template['nodes'][0]['params']['width'] = 200
template['nodes'][0]['params']['length'] = 100
template['nodes'][0]['params']['height'] = 60
```

---

### 4. sphere_with_preview.json

**Purpose:** Create a sphere with preview control  
**Strategy:** Native Node  
**Use Case:** Intermediate geometry for boolean operations

```json
{
  "nodes": [{
    "id": "sphere_preview",
    "name": "Sphere.ByCenterPointRadius",
    "params": {
      "centerPoint": "Point.ByCoordinates(0,0,0);",
      "radius": 50
    },
    "x": 500,
    "y": 300,
    "preview": false,
    "_comment": "Intermediate geometry, hidden for boolean operations"
  }],
  "connectors": []
}
```

**Modification Example:**
```python
template['nodes'][0]['params']['radius'] = 100
template['nodes'][0]['preview'] = True  # Show in viewport
```

---

## Python Script Templates

### 5. python_basic.json

**Purpose:** Empty Python Script node template  
**Strategy:** Python Script injection  
**Use Case:** Quick starting point for custom scripts

```json
{
  "nodes": [{
    "id": "py_basic",
    "name": "Python Script",
    "pythonCode": "# Your Python code here\n# Input: IN[0]\n# Output: OUT\n\nOUT = IN[0]",
    "x": 500,
    "y": 300
  }],
  "connectors": []
}
```

**Modification Example:**
```python
template['nodes'][0]['pythonCode'] = """
# Custom calculation
result = IN[0] * 2
OUT = result
"""
```

---

### 6. python_revit_rooms.json

**Purpose:** Read Revit room names  
**Strategy:** Python Script with Revit API  
**Use Case:** Extract BIM data from Revit models

```json
{
  "nodes": [{
    "id": "py_revit_rooms",
    "name": "Python Script",
    "pythonCode": "import clr\nclr.AddReference('RevitAPI')\nfrom Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory\n\n# Get active document\ndoc = IN[0]\n\n# Collect all rooms\nrooms = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType()\n\n# Extract room names\nroom_names = [r.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() for r in rooms]\n\nOUT = room_names",
    "x": 500,
    "y": 300
  }],
  "connectors": []
}
```

**Modification Example:**
```python
# Adapt for walls instead of rooms
template['nodes'][0]['pythonCode'] = """
import clr
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

doc = IN[0]
walls = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls)
OUT = [w.Name for w in walls]
"""
```

---

## Connection Templates

### 7. connection_workflow.json

**Purpose:** Complete workflow with node connection  
**Strategy:** Select Element → Python Script  
**Use Case:** Interactive element processing

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
      "pythonCode": "# Process selected element\nelement = IN[0]\n\n# Extract element properties\nproperties = {\n    'Name': element.Name,\n    'Id': element.Id.IntegerValue,\n    'Category': element.Category.Name\n}\n\nOUT = properties",
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

**Modification Example:**
```python
# Change Python processing logic
template['nodes'][1]['pythonCode'] = """
element = IN[0]
OUT = element.Name  # Just return name
"""

# Add more connections
template['connectors'].append({
    "from": "py_script",
    "to": "another_node",
    "fromPort": 0,
    "toPort": 0
})
```

---

## Usage Patterns

### Pattern 1: Load and Execute Directly

```python
import json

with open('.skills/dynamo-automation/assets/templates/point_basic.json') as f:
    template = json.load(f)

await execute_dynamo_instructions(json.dumps(template))
```

---

### Pattern 2: Load, Modify, Execute

```python
import json

# Load template
with open('.skills/dynamo-automation/assets/templates/cuboid_parameterized.json') as f:
    template = json.load(f)

# Modify parameters
template['nodes'][0]['params']['width'] = 200
template['nodes'][0]['x'] = 600  # Change position

# Execute
await execute_dynamo_instructions(json.dumps(template))
```

---

### Pattern 3: Combine Multiple Templates

```python
import json

# Load two templates
with open('.skills/dynamo-automation/assets/templates/point_basic.json') as f:
    pt_template = json.load(f)

with open('.skills/dynamo-automation/assets/templates/cuboid_parameterized.json') as f:
    cube_template = json.load(f)

# Combine nodes
combined = {
    "nodes": pt_template['nodes'] + cube_template['nodes'],
    "connectors": []
}

await execute_dynamo_instructions(json.dumps(combined))
```

---

## Template Selection Guide

| User Request | Recommended Template | Reason |
|:---|:---|:---|
| "Create a point" | `point_basic.json` | Simple, fixed coordinates |
| "Draw a line from A to B" | `line_nested.json` | Nested geometry example |
| "Make a box 100x50x30" | `cuboid_parameterized.json` | Parameterized, adjustable |
| "Add a hidden sphere" | `sphere_with_preview.json` | Preview control |
| "Run Python code" | `python_basic.json` | Quick starting point |
| "Get room names" | `python_revit_rooms.json` | Revit-specific task |
| "Process selected element" | `connection_workflow.json` | Interactive workflow |

---

## Creating Custom Templates

### Step 1: Start from existing template

Choose the closest match to your use case.

### Step 2: Modify structure

```python
custom_template = {
    "nodes": [{
        "id": "my_custom_node",
        "name": "NodeType",
        "params": {...},  # If Native Node
        "value": "...",   # If Code Block
        "x": 500,
        "y": 300
    }],
    "connectors": []
}
```

### Step 3: Test

```python
await execute_dynamo_instructions(json.dumps(custom_template))
```

### Step 4: Save to library (optional)

```python
await save_to_library("my_custom_template", json.dumps(custom_template))
```

---

## Related Documentation

- **Quick Start Guide:** [quick-start.md](quick-start.md)
- **Node Creation Strategies:** [../../domain/node_creation_strategy.md](../../domain/node_creation_strategy.md)
- **Python Script Automation:** [../../domain/python_script_automation.md](../../domain/python_script_automation.md)
- **Node Connection Workflow:** [../../domain/node_connection_workflow.md](../../domain/node_connection_workflow.md)

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-24  
**Maintained by:** Dynamo MCP Team
