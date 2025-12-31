from mcp.server.fastmcp import FastMCP
import time

# 初始化 Server
mcp = FastMCP("BIM_Assistant")

# ==========================================
# 既有工具 (保留)
# ==========================================
@mcp.tool()
def add(a: int, b: int) -> int:
    """Basic addition."""
    return a + b

@mcp.tool()
def get_material_specs(material_name: str) -> dict:
    """Mock database search for materials."""
    db = {"Concrete": 2400, "Steel": 7850}
    val = db.get(material_name, 0)
    return {"density": val, "unit": "kg/m3"}

# ==========================================
# 新增工具: AI 顧問
# ==========================================
@mcp.tool()
def ask_ai_consultant(question: str, context: str = "") -> str:
    """
    Ask the AI Consultant a question about BIM, Revit API, or Dynamo strategies.
    
    Args:
        question: The user's question (e.g., "How do I filter walls by height?").
        context: Optional background info (e.g., list of current node names).
        
    Returns:
        A text advice string.
    """
    # 模擬思考時間，增加真實感
    time.sleep(1)
    
    q_lower = question.lower()
    
    # 這裡未來可以替換成 OpenAI / Gemini API call
    # response = openai.ChatCompletion.create(...)
    
    # 目前的模擬邏輯 (Mock Logic)
    if "filter" in q_lower and "wall" in q_lower:
        return (
            "💡 **AI 建議**: 若要篩選牆，建議使用 `Element.GetParameterValueByName` "
            "讀取 'Unconnected Height'，然後搭配 `List.FilterByBoolMask`。\n"
            "若要過濾類型，請使用 `Element.Name` 節點。"
        )
    
    elif "warning" in q_lower or "error" in q_lower:
        return (
            "⚠️ **Debug 建議**: 遇到黃色警告通常是資料結構問題 (List Level)。"
            "請檢查您的輸入是否需要 `List.Flatten`，或者改變節點的 L2/L3 設定。"
        )
        
    elif "python" in q_lower:
        return (
            "🐍 **Python 提示**: 在 Dynamo Python Node 中，請記得 `UnwrapElement(IN[0])` "
            "才能呼叫 Revit API 的原生方法。"
        )
        
    elif "api" in q_lower:
        return (
            "📘 **API 知識**: Revit API 中，修改模型必須在 `Transaction` 內進行。"
            "雖然 Dynamo 節點通常自動處理，但在 Python Script 中要特別注意 TransactionManager。"
        )

    # 預設回應
    return (
        f"🤖 **AI 收到問題**: '{question}'\n"
        f"目前我尚未連接真實的 LLM (如 GPT-4)，但您可以問我關於 'filter walls', 'python script', 或 'api' 的問題來測試我的關鍵字觸發功能。"
    )

import json
import urllib.request
import urllib.error

# ==========================================
# 新增工具: Dynamo 自動化操作
# ==========================================
@mcp.tool()
def execute_dynamo_instructions(instructions: str) -> str:
    """
    Execute a set of instructions to create nodes and connections in Dynamo.
    
    Args:
        instructions: A JSON string describing the nodes and connections.
                      Example:
                      {
                        "nodes": [
                          {"id": "n1", "name": "Point.ByCoordinates", "x": 0, "y": 0},
                          {"id": "n2", "name": "Number", "value": 10, "x": -100, "y": 0}
                        ],
                        "connectors": [
                          {"from": "n2", "to": "n1", "fromPort": 0, "toPort": 0}
                        ]
                      }
                      
    Returns:
        Status message.
    """
    url = "http://127.0.0.1:5050/mcp/"
    
    try:
        # Validate JSON
        try:
            json.loads(instructions)
        except json.JSONDecodeError:
            return "Error: Invalid JSON format."

        req = urllib.request.Request(
            url, 
            data=instructions.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return f"Successfully sent instructions to Dynamo. Response: {response.read().decode('utf-8')}"
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return f"Dynamo Server Error ({e.code}): {error_body}"
    except urllib.error.URLError as e:
        return f"Failed to connect to Dynamo. Please ensure the Dynamo View Extension is installed and Dynamo is running. Error: {e}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

# ==========================================
# 新增工具: 列出可用節點
# ==========================================
@mcp.tool()
def list_available_nodes(filter_text: str = "", search_scope: str = "default", detail: str = "basic") -> str:
    """
    List available nodes in the current Dynamo session, including .dyf custom nodes from packages.
    
    Args:
        filter_text: Optional text to filter node names.
        search_scope: "default" (Recommended) searches Common Nodes + matches from Global list (limit 20).
                      "all" searches entire Global Node Library (limit 200). 
                      Use "all" ONLY if the user explicitly asks to "search all nodes" or "global search".
        detail: Level of detail to return:
                "basic" (default) - Only name and fullName (fastest, lowest tokens)
                "standard" - Adds inputs, outputs, and category (includes .dyf metadata)
                "full" - Includes description (highest tokens)
        
    Returns:
        JSON string of available nodes with metadata.
    """
    url = "http://127.0.0.1:5050/mcp/"
    payload = json.dumps({
        "action": "list_nodes", 
        "filter": filter_text,
        "scope": search_scope,
        "detail": detail
    })
    
    try:
        req = urllib.request.Request(
            url, 
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
            
    except Exception as e:
        return f"Error listing nodes: {str(e)}"


@mcp.tool()
def analyze_workspace() -> str:
    """
    Get the current state of all nodes in the Dynamo workspace, including errors and warnings.
    
    Returns:
        JSON string containing node names and their execution states.
    """
    url = "http://127.0.0.1:5050/mcp/"
    payload = json.dumps({"action": "get_graph_status"})
    
    try:
        req = urllib.request.Request(
            url, 
            data=payload.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
            
    except Exception as e:
        return f"Error analyzing workspace: {str(e)}. Make sure the latest Dynamo Extension is deployed."



# ==========================================
# 新增工具: 腳本庫管理 (Script Library)
# ==========================================
import os
import glob

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "DynamoScripts")
# 也可考慮存放在使用者的 AppData 以便持久化，但目前維持在專案夾內
if not os.path.exists(SCRIPT_DIR):
    os.makedirs(SCRIPT_DIR)

@mcp.tool()
def get_script_library() -> str:
    """
    Get a list of available scripts in the library.
    
    Scripts are stored in: <PROJECT_ROOT>/DynamoScripts/
    All .json files in this directory are automatically discovered.
    
    Returns:
        JSON string list of script metadata (name, description, file path).
    """
    scripts = []
    try:
        files = glob.glob(os.path.join(SCRIPT_DIR, "*.json"))
        for f in files:
            name = os.path.basename(f).replace(".json", "")
            desc = "No description"
            try:
                with open(f, "r", encoding="utf-8") as rf:
                    data = json.load(rf)
                    desc = data.get("description", "No description")
            except:
                pass
            scripts.append({
                "name": name, 
                "description": desc,
                "path": f
            })
        return json.dumps(scripts, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error reading library: {str(e)}"

@mcp.tool()
def save_script_to_library(name: str, description: str, content_json: str) -> str:
    """
    Save a Dynamo script to the library for future reuse.
    
    Files are saved to: <PROJECT_ROOT>/DynamoScripts/<name>.json
    This folder is the central repository for reusable Dynamo graph definitions.
    
    Args:
        name: Unique name for the script (e.g., 'grid_2x2').
        description: Brief description of what the script does.
        content_json: The JSON instructions for nodes and connectors.
        
    Returns:
        Success message with absolute file path, or error message.
    """
    try:
        # Validate content JSON
        content = json.loads(content_json)
        
        file_path = os.path.join(SCRIPT_DIR, f"{name}.json")
        data = {
            "description": description,
            "content": content
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        abs_path = os.path.abspath(file_path)
        return f"Script '{name}' saved successfully to: {abs_path}"
    except Exception as e:
        return f"Error saving script: {str(e)}"

@mcp.tool()
def load_script_from_library(name: str) -> str:
    """
    Load a Dynamo script content from the library.
    
    Loads from: <PROJECT_ROOT>/DynamoScripts/<name>.json
    The returned JSON can be directly passed to execute_dynamo_instructions.
    
    Args:
        name: The name of the script to load (without .json extension).
        
    Returns:
        The content JSON string (nodes and connectors) ready for execution.
        Returns error message if script not found.
    """
    try:
        file_path = os.path.join(SCRIPT_DIR, f"{name}.json")
        if not os.path.exists(file_path):
            return f"Error: Script '{name}' not found."
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # We return the inner content which is what execute_dynamo_instructions expects
            return json.dumps(data.get("content", {}))
    except Exception as e:
        return f"Error loading script: {str(e)}"

if __name__ == "__main__":
    print("Starting BIM Assistant MCP Server (Version 2.2)...")
    mcp.run(transport="sse")
