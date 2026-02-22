
import sys
import os
import json
import asyncio

# Ensure tools directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mcp_client import call_tool

# Set stdout encoding to utf-8
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

async def main():
    if len(sys.argv) < 3:
        print("Usage: python run_tool.py <tool_name> <args_json_string_or_file>")
        return

    tool_name = sys.argv[1]
    arg_input = sys.argv[2]
    
    args = {}
    
    # 1. Try to parse as JSON string first (heuristic: starts with {)
    if arg_input.strip().startswith("{"):
        try:
            parsed = json.loads(arg_input)
            # Special handling for execute_dynamo_instructions which expects "instructions" string
            if tool_name == "execute_dynamo_instructions" and "nodes" in parsed:
                args = {"instructions": arg_input}
            else:
                args = parsed
        except json.JSONDecodeError:
            print("Error: Invalid JSON string")
            return
            
    # 2. Try to read from file
    elif os.path.exists(arg_input):
        try:
            with open(arg_input, 'r', encoding='utf-8-sig') as f:
                content = json.load(f)
                
            if tool_name == "execute_dynamo_instructions" and "nodes" in content:
                # Wrap the content back into a string for the tool
                args = {"instructions": json.dumps(content, ensure_ascii=False)}
            else:
                args = content
        except Exception as e:
            print(f"Error reading file {arg_input}: {e}")
            return
    else:
        print(f"Error: Argument is neither a valid JSON string nor an existing file: {arg_input}")
        return

    # print(f"Calling tool: {tool_name}...")
    result = await call_tool(tool_name, args)
    
    if result is None:
        print("Error: Tool execution failed (returned None). Check server connection.")
    else:
        # Check if result is double-encoded JSON string (common in this project)
        if isinstance(result, str):
            try:
                # Try to parse it to pretty print, otherwise print raw
                parsed_res = json.loads(result)
                print(json.dumps(parsed_res, indent=2, ensure_ascii=False))
            except:
                print(result)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
