# --- COPY FROM HERE ---
import clr
import System
import sys

clr.AddReference("System.Core")
clr.AddReference("DynamoServices")

output = []
output.append("=== DYNAMO ENVIRONMENT DIAGNOSIS ===")

# 1. Check Runtime Version
version = System.Environment.Version.ToString()
output.append("CLR Version: " + version)
if version.startswith("4."):
    output.append("⚠️ WARNING: You are running on .NET Framework 4.8 (Old Dynamo/Revit 2024).")
    output.append("   This extension requires .NET 8 (Dynamo 3.0+ / Revit 2025).")
else:
    output.append("✅ .NET Runtime looks like .NET Core/6+/8+.")

# 2. Check Loaded Assemblies
output.append("\n--- Loaded Assemblies Checking ---")
assemblies = System.AppDomain.CurrentDomain.GetAssemblies()
mcp_found = False
newtonsoft_loc = "Not Found"

for asm in assemblies:
    name = asm.GetName().Name
    if "DynamoMCPListener" in name:
        mcp_found = True
        output.append("✅ FOUND DynamoMCPListener!")
        output.append("   - Location: " + asm.Location)
        output.append("   - Version: " + str(asm.GetName().Version))
    if "Newtonsoft.Json" in name:
        newtonsoft_loc = asm.Location

if not mcp_found:
    output.append("❌ DynamoMCPListener assembly NOT loaded in this AppDomain.")
    output.append("   (This explains why StartMCPServer works but ViewExtension doesn't - separate contexts?)")

output.append(f"ℹ️ Newtonsoft.Json Location: {newtonsoft_loc}")

# 3. Check Environment Path
# output.append("\n--- Path Info ---")
# output.append("AppData: " + System.Environment.GetFolderPath(System.Environment.SpecialFolder.ApplicationData))

OUT = "\n".join(output)
# --- END COPY ---
