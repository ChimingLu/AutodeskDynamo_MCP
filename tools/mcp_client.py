
import asyncio
import json
import websockets

URI = "ws://127.0.0.1:65296"

async def send_jsonrpc(method, params, uri=URI):
    """
    Send a JSON-RPC request to the MCP server via WebSocket.
    """
    try:
        async with websockets.connect(uri) as ws:
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            }
            await ws.send(json.dumps(request))
            response = await ws.recv()
            return json.loads(response)
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        return None

async def call_tool(tool_name, args={}, uri=URI):
    """
    Call an MCP tool and return the result.
    Handles error printing.
    """
    resp = await send_jsonrpc("tools/call", {"name": tool_name, "arguments": args}, uri)
    
    if not resp:
        return None
        
    if "error" in resp:
        print(f"[ERROR] {tool_name}: {resp['error']}")
        return None
        
    result = resp.get("result")
    
    # Common pattern: result might be a JSON string that needs parsing
    # But usually tool returns dict. If it returns string, we let caller handle?
    # No, let's keep it raw for now to match original logic which handled it ad-hoc.
    return result

async def list_tools(uri=URI):
    """
    List available tools.
    """
    resp = await send_jsonrpc("tools/list", {}, uri)
    if not resp:
        return None
    return resp.get("result", {})
