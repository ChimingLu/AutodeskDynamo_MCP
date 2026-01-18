# --- COPY FROM HERE ---
import clr
import System
import sys

# Ensure Standard Libraries are loaded
clr.AddReference("System.Core")
clr.AddReference("System.Reflection")

output = []
output.append("=== REFLECTION DIAGNOSIS ===")

domain = System.AppDomain.CurrentDomain
target_asm = None

# 1. Find the Assembly
for asm in domain.GetAssemblies():
    if "DynamoMCPListener" in asm.GetName().Name:
        target_asm = asm
        break

if not target_asm:
    output.append("❌ ASSEMBLY NOT FOUND! (This is critical)")
else:
    output.append(f"✅ Assembly Found: {target_asm.FullName}")
    output.append(f"   Location: {target_asm.Location}")
    
    # 2. Inspect Types
    output.append("\n--- Type Inspection ---")
    try:
        types = target_asm.GetTypes()
        view_ext_type = None
        for t in types:
            if "ViewExtension" in t.Name:
                view_ext_type = t
                output.append(f"✅ Found Class: {t.FullName}")
                output.append(f"   Is Public: {t.IsPublic}")
                output.append(f"   Is Interface: {t.IsInterface}")
                
                # Check Interface implementation
                interfaces = t.GetInterfaces()
                found_iview = False
                for iface in interfaces:
                    output.append(f"   -> Implements: {iface.Name}")
                    if "IViewExtension" in iface.Name:
                        found_iview = True
                
                if found_iview:
                    output.append("   ✅ Correctly implements IViewExtension")
                else:
                    output.append("   ❌ MISSING IViewExtension implementation!")

    except Exception as e:
        output.append(f"❌ REFLECTION ERROR (Loader Exception): {e}")
        if hasattr(e, "LoaderExceptions"):
            for le in e.LoaderExceptions:
                output.append(f"   -> {le}")

OUT = "\n".join(output)
# --- END COPY ---
