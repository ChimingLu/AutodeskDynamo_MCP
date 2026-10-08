# GitHub Copilot Instructions for Autodesk Dynamo MCP
🗣️ 語言要求
**所有與使用者的互動、程式碼建議、技術討論和說明文件都必須使用繁體中文 (zh-Tw) ** 這包括：

程式碼註解和文字字串

執行程式碼禁止使用emoji，避免造成程式執行錯誤

錯誤訊息和使用者介面文字

技術討論和架構說明

Commit 訊息和 Pull Request 描述

程式碼審查意見

Implementation Plan (實作計畫) 的撰寫

Task (任務) 的描述和追蹤

所有互動式文件和說明
## Project Overview

**Autodesk Dynamo MCP Integration** bridges AI agents to Autodesk Dynamo via Model Context Protocol (MCP), enabling automated BIM modeling and querying. The system uses a **Stdin+WebSocket hybrid architecture**:

```
AI Client (Stdio/MCP) → Node.js Bridge → Python Manager (WS) → Dynamo C# Extension (WS)
```

## Architecture & Key Files

### Core Bridge Components

- **[bridge/python/server.py](../bridge/python/server.py)** - MCP processor + WebSocket server (port 65296 for AI, 65535 for Dynamo)
- **[bridge/node/index.js](../bridge/node/index.js)** - Stdio-to-WS adapter for AI clients (Gemini, Claude)
- **[DynamoViewExtension/src/](../DynamoViewExtension/src/)** - C# extension handling graph manipulation

### Knowledge & Configuration

- **[domain/](../domain/)** - SOP knowledge base with technical strategies and workflows
  - `node_creation_strategy.md` - Dual-track node placement (Code Block vs Native Nodes)
  - `python_script_automation.md` - Python injection into Dynamo nodes
  - `node_connection_workflow.md` - Cross-language ID mapping for connections
  - `startup_checklist.md` - Initialization sequence
  - `troubleshooting.md` - Ghost connection fixes, connection refused solutions
- **[GEMINI.md](../GEMINI.md)** - AI behavioral rules & context engineering patterns
- **[QUICK_REFERENCE.md](../QUICK_REFERENCE.md)** - Essential commands and common scenarios
- **[mcp_config.json](../mcp_config.json)** - Central configuration (ports, paths, deployment info)

## Critical Workflows

### 1. Node Creation: Dual-Track Strategy

Always check [domain/node_creation_strategy.md](../domain/node_creation_strategy.md) before implementing node placement.

**Track A (Code Block - 100% reliable)**
- Use for simple geometry: `Point.ByCoordinates(0,0,0);`
- Use for complex nesting: `Solid.Difference(...)`
- Use as fallback when Track B fails
- JSON template: `{"name": "Number", "value": "DesignScript code;", "x": 300, "y": 300}`

**Track B (Native Nodes - parameter-driven)**
- Use for interactive visualizations
- Requires explicit `overload` and `preview` settings
- Provides multi-step debugging capability
- Automatic fallback to Track A on connection failure

### 2. Python Script Automation

See [domain/python_script_automation.md](../domain/python_script_automation.md) for three-layer reflection mechanism.

- Auto-place Python Script nodes in Dynamo
- Inject code via reflection (not UI)
- Auto-switch to CPython3 engine
- Handle code-to-UI synchronization

### 3. Node Connection

Reference [domain/node_connection_workflow.md](../domain/node_connection_workflow.md) for ID mapping.

- Use `toPortName` (e.g., "z") for robust port matching vs brittle index-based connections
- C# automatically handles Overload fallback when port names don't match
- Validate connection setup with `analyze_workspace` after execution

## Essential MCP Tools

All tools are exposed via `server.py` and bridged through Node.js:

| Tool | Purpose | Key Param |
|------|---------|-----------|
| `execute_dynamo_instructions` | Place nodes & connectors | `instructions` (JSON string with `nodes`/`connectors`) |
| `analyze_workspace` | Query current graph state | None - returns node list, errors, status |
| `clear_workspace` | Wipe canvas | None - use `clear_before_execute=true` to avoid overlaps |
| `get_node_pattern` | **Call first** for common node chains; returns ready-to-execute JSON | `query` (e.g., "品類 視圖 元件") |
| `get_node_recipe` | **Call before building** — verified create names, ports, gotchas | `names` (list) |
| `search_nodes` | Find nodes missing from the registry (use the `create` field) | `query` (e.g., "Room", "Solid") |
| `save_node_pattern` / `capture_node_pattern` | Remember a working node chain (from executed JSON / from the user's selection in Dynamo) | `name`, `instructions` or selection |
| `get_mcp_guidelines` | Retrieve [GEMINI.md](../GEMINI.md) content | None - returns full spec |

## Developer Workflows

### Build & Deployment

```powershell
# One-click build + install to Dynamo packages
.\deploy.ps1

# Manual build (C#)
cd DynamoViewExtension
dotnet build
```

### Start MCP Server

```bash
# Terminal 1: Python MCP Manager (handles WebSocket bridging)
python bridge/python/server.py

# Terminal 2: AI client uses pre-configured MCP in Claude/Gemini
# No manual startup needed - they connect to Python server via Node.js bridge
```

### Verify Connection

```python
# From examples/demo_analyze_workspace.py
python examples/demo_analyze_workspace.py
# Should return workspace JSON if Dynamo is open & connected
```

## Project Conventions

### File Organization

- **`domain/`** - Long-term business logic, SOP strategies (MD format)
- **`DynamoScripts/`** - Stable, reusable Dynamo JSON graphs
- **`examples/`** - Parameterized, callable workflows (PY format with `demo_` prefix)
- **`tests/`** - Task-driven, debug-only scripts (suffix `_test.py`)
- **`image/`** - `/image` command output (Mermaid diagrams, technical docs)

### Code Style

- **C#**: 4-space indent, XML doc comments, follow Microsoft conventions
- **Python**: PEP 8, 4-space indent, type hints, docstrings for functions
- **JSON (Dynamo graphs)**: Indented structure, required fields: `nodes[]`, `connectors[]`, `id`, `name`, `x`, `y`

### Documentation Sync Rule

When updating `README.md`, **always sync** `README_EN.md` with same content (translations maintained separately).

## Anti-Patterns to Avoid

1. **Ghost Connections** - Nodes created but invisible on canvas
   - Solution: Run `analyze_workspace` to verify; use BIM Assistant menu to reconnect
2. **Brittle Port Indexing** - Using `fromIndex`/`toIndex` instead of `fromPort`/`toPort`
   - Solution: Always use `toPortName` for port matching (e.g., `"z"` for Z coordinate)
3. **Overload Ambiguity** - Not specifying node overload (e.g., "2D" vs "3D")
   - Solution: Always set `"overload": "3D"` for 3D nodes; C# auto-handles fallback
4. **Hardcoded Ports** - Assuming port numbers don't change across Dynamo versions
   - Solution: Use fallback port name matching; verify with `search_nodes` first
5. **Missing Code Block Semicolons** - DesignScript code without trailing `;`
   - Solution: Track A always requires `"value": "...;"` format

## Debugging Checklist

- ✅ **Connection refused?** Ensure `python bridge/python/server.py` is running (port 65296)
- ✅ **Nodes not visible?** Run `analyze_workspace` to check for ghost connections
- ✅ **Port mismatch errors?** Check [domain/node_connection_workflow.md](../domain/node_connection_workflow.md) for fallback rules
- ✅ **Python script not running?** Verify CPython3 engine is set via `python_script_automation.md`
- ✅ **Dynamo crash?** Check logs in `logs/` folder; see [domain/troubleshooting.md](../domain/troubleshooting.md)

## Auto-Initialization Requirements

Before any modeling task, agents **must**:

1. Call `analyze_workspace` to verify connection state
2. Check [GEMINI.md](../GEMINI.md) for current rules
3. Review `domain/` for relevant SOP (e.g., if placing Python scripts, read `python_script_automation.md`)
4. Use `get_mcp_guidelines()` to load live specs into context

## References

- Architecture details: [domain/architecture_analysis.md](../domain/architecture_analysis.md)
- AI behavior rules: [GEMINI.md](../GEMINI.md) (Section "AI 協作指令")
- Contribution guide: [CONTRIBUTING.md](../CONTRIBUTING.md)
- Quick answers: [QUICK_REFERENCE.md](../QUICK_REFERENCE.md)
