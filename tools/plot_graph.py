
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

def generate_graph_plot(input_file="tests/workspace_full.json", output_file="image/maximize_view_graph.png"):
    try:
        # Load JSON data
        # Try different encodings
        content = ""
        for enc in ['utf-16', 'utf-8', 'utf-16-le', 'cp1252', 'utf-16-be']:
            try:
                with open(input_file, 'r', encoding=enc) as f:
                    content = f.read()
                    if content.strip().startswith('{') or content.strip().startswith('['):
                        break
            except:
                continue
        
        if not content.strip():
            print("Failed to read/decode JSON")
            return
            
        # Clean BOM
        content = content.replace('\ufeff', '')
            
        data = {}
        try:
            data = json.loads(content)
            if isinstance(data, str):
                data = json.loads(data)
        except Exception as e:
            # Last ditch effort
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    data = json.loads(content[start:end])
            except:
                print(f"JSON parsing failed: {e}")
                print(f"Content snippet: {content[:100]}")
                return

        nodes = data.get("nodes", [])
        connectors = data.get("connectors", [])
        
        if not nodes:
            print("No nodes found")
            return

        # Prepare plot
        fig, ax = plt.subplots(figsize=(16, 9))
        ax.set_facecolor('#1e1e1e')  # Dark theme background
        fig.patch.set_facecolor('#1e1e1e')

        # Node coordinates
        xs = [float(n.get("x", 0)) for n in nodes]
        ys = [float(n.get("y", 0)) for n in nodes]
        
        # Draw connectors first (behind nodes)
        node_lookup = {n["id"]: (float(n.get("x",0)), float(n.get("y",0))) for n in nodes}
        
        for conn in connectors:
            start_pos = node_lookup.get(conn["from"])
            end_pos = node_lookup.get(conn["to"])
            
            if start_pos and end_pos:
                # Calculate control points for bezier-like curves (simple straight line for now or cubic)
                # Drawing simple lines with alpha
                ax.plot([start_pos[0], end_pos[0]], [start_pos[1], end_pos[1]], 
                        color='#4a4a4a', alpha=0.9, linewidth=0.8, zorder=1)

        # Draw nodes
        # Color nodes based on type (heuristic)
        colors = []
        sizes = []
        labels = []
        
        for n in nodes:
            name = n.get("name", "Node")
            if "Input" in name or "Selection" in name or "Select" in name:
                colors.append('#00bcd4') # Cyan for Input
                sizes.append(150)
            elif "Output" in name or "Watch" in name or "Color" in name:
                colors.append('#e91e63') # Pink for Output
                sizes.append(150)
            elif "Python" in name:
                 colors.append('#ffeb3b') # Yellow for Script
                 sizes.append(200)
            else:
                colors.append('#b0bec5') # Grey for default
                sizes.append(80)
            
            # Add text label for significant nodes
            if sizes[-1] > 100 or len(nodes) < 50:
                 ax.text(float(n.get("x",0)), float(n.get("y",0))+15, name, 
                        color='white', fontsize=6, ha='center', va='bottom', zorder=3)

        scatter = ax.scatter(xs, ys, s=sizes, c=colors, alpha=1.0, zorder=2, edgecolors='none')

        # Title and styling
        file_name = data.get("FileName", "Home")
        title_text = f"Dynamo Graph Analysis: {file_name}\nNodes: {len(nodes)} | Connectors: {len(connectors)}"
        
        plt.title(title_text, color='white', fontsize=14, pad=20)
        plt.axis('off')  # Hide axis
        
        # Save output
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
        print(f"Graph plot saved to {output_file}")
        
    except Exception as e:
        print(f"Plotting failed: {e}")

if __name__ == "__main__":
    generate_graph_plot(output_file="image/maximize_view_graph.png")
