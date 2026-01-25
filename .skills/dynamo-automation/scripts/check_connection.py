#!/usr/bin/env python3
"""
Quick Connection Check for Dynamo MCP

This script performs a fast diagnostics check to verify MCP server connectivity
and workspace status.

Usage:
    python check_connection.py
"""

import sys
import os
import asyncio

# Add bridge directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../../../"))
bridge_path = os.path.join(project_root, "bridge/python")
sys.path.insert(0, bridge_path)

try:
    # Import MCP client functionality
    # Note: This assumes the bridge/python/server.py exports necessary functions
    import json
    import http.client
    
    async def check_connection():
        """Check MCP server connection and workspace status"""
        try:
            # Simulate MCP call to analyze_workspace
            # In production, this would use actual MCP client
            conn = http.client.HTTPConnection("127.0.0.1", 65535, timeout=5)
            
            request_data = json.dumps({"action": "analyze_workspace"})
            headers = {'Content-Type': 'application/json'}
            
            conn.request("POST", "/mcp/", request_data, headers)
            response = conn.getresponse()
            result = json.loads(response.read().decode())
            
            if response.status == 200:
                print("✅ MCP Connection: SUCCESS")
                print(f"📊 Workspace: {result.get('workspaceName', 'Unknown')}")
                print(f"📄 File: {result.get('workspaceFileName', 'Not saved')}")
                print(f"🔢 Nodes: {result.get('nodeCount', 0)}")
                print(f"🔗 Connectors: {result.get('connectorCount', 0)}")
                return 0
            else:
                print(f"❌ MCP Connection: FAILED (Status {response.status})")
                return 1
                
        except ConnectionRefusedError:
            print("❌ Connection Refused")
            print("💡 Is the Python server running? Try: python bridge/python/server.py")
            return 1
        except TimeoutError:
            print("❌ Connection Timeout")
            print("💡 Check if Dynamo is open and responsive")
            return 1
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            return 1
    
    if __name__ == "__main__":
        exit_code = asyncio.run(check_connection())
        sys.exit(exit_code)
        
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("💡 Make sure you're running this from the project root")
    sys.exit(1)
