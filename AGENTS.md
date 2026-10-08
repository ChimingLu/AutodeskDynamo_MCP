# Agent Instructions

This repo controls Autodesk Dynamo through the `dynamo-mcp` MCP server (`bridge/node/index.js` → `bridge/python/server.py`).

- Full guide for all agents: [docs/ai-guide/quick-start.md](docs/ai-guide/quick-start.md); rules: [GEMINI.md](GEMINI.md) (also returned by the `get_mcp_guidelines` tool).
- **Node registry first**: before building a graph call `get_node_pattern(query)` for common node chains and `get_node_recipe(names)` for every node; use `search_nodes` only for misses. All agents share `domain/node_registry.json`.
- **Remember what works**: after a reusable chain executes successfully, call `save_node_pattern` with the same instructions JSON; for a chain the user built by hand, have them save the `.dyn`, select the nodes, then call `capture_node_pattern`.
- Use GUID node ids; never delete nodes or modify the workspace from inside a Python node.
