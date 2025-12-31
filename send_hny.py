import json
import urllib.request

def send_to_dynamo(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # The server expects the 'content' part
    instructions = json.dumps(data["content"])
    
    url = "http://127.0.0.1:5050/mcp/"
    
    req = urllib.request.Request(
        url, 
        data=instructions.encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Successfully sent instructions to Dynamo. Response: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_to_dynamo("DynamoScripts/happy_new_year.json")
