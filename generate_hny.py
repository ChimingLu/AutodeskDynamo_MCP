import json

def get_letter_points(char, base_x, base_y):
    letters = {
        'H': [(0,0), (0,1), (0,2), (0,3), (0,4), (4,0), (4,1), (4,2), (4,3), (4,4), (1,2), (2,2), (3,2)],
        'A': [(0,0), (0,1), (0,2), (0,3), (1,4), (2,4), (3,4), (4,3), (4,2), (4,1), (4,0), (1,2), (2,2), (3,2)],
        'P': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,4), (2,4), (3,4), (4,3), (4,2), (3,2), (2,2), (1,2)],
        'Y': [(0,4), (1,3), (2,2), (3,3), (4,4), (2,1), (2,0)],
        'N': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,3), (2,2), (3,1), (4,0), (4,1), (4,2), (4,3), (4,4)],
        'E': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,0), (2,0), (3,0), (4,0), (1,2), (2,2), (3,2), (1,4), (2,4), (3,4), (4,4)],
        'W': [(0,4), (0,3), (0,2), (0,1), (1,0), (2,1), (3,0), (4,1), (4,2), (4,3), (4,4)],
        'R': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,4), (2,4), (3,4), (4,3), (4,2), (3,2), (2,2), (1,2), (2,1), (3,0), (4,0)],
        'Y': [(0,4), (1,3), (2,2), (3,3), (4,4), (2,1), (2,0)],
        '!': [(2,4), (2,3), (2,2), (2,0)],
        '2': [(0,4), (1,4), (2,4), (3,4), (4,4), (4,3), (4,2), (3,2), (2,2), (1,2), (0,2), (0,1), (0,0), (1,0), (2,0), (3,0), (4,0)],
        '0': [(0,0), (0,1), (0,2), (0,3), (0,4), (1,4), (2,4), (3,4), (4,4), (4,3), (4,2), (4,1), (4,0), (1,0), (2,0), (3,0)],
        '5': [(4,4), (3,4), (2,4), (1,4), (0,4), (0,3), (0,2), (1,2), (2,2), (3,2), (4,2), (4,1), (4,0), (3,0), (2,0), (1,0), (0,0)],
        '6': [(4,4), (3,4), (2,4), (1,4), (0,4), (0,3), (0,2), (0,1), (0,0), (1,0), (2,0), (3,0), (4,0), (4,1), (4,2), (3,2), (2,2), (1,2)],
    }
    
    raw_pts = letters.get(char.upper(), [])
    return [(base_x + x, base_y + y) for x, y in raw_pts]

def generate_hny_designscript():
    lines = ["HAPPY", "NEW", "YEAR", "2026!"]
    
    char_spacing = 6
    row_spacing = 8
    
    ds_lines = []
    ds_lines.append("// Happy New Year 2026 - Premium Geometry")
    ds_lines.append("r_base = 0.4;")
    
    all_letter_points = []
    for row_idx, line in enumerate(lines):
        for char_idx, char in enumerate(line):
            base_x = char_idx * char_spacing
            base_y = -row_idx * row_spacing
            points = get_letter_points(char, base_x, base_y)
            all_letter_points.extend(points)
    
    # Create letter spheres
    pt_strings = []
    for i, (x, y) in enumerate(all_letter_points):
        # Add some slight variation in Z for depth
        z = (x % 3) * 0.2
        pt_strings.append(f"Point.ByCoordinates({x}, {y}, {z:.2f})")
    
    ds_lines.append("letter_pts = [" + ",\n".join(pt_strings) + "];")
    ds_lines.append("letter_spheres = Sphere.ByCenterPointRadius(letter_pts, r_base);")
    
    # Add some "fireworks"
    ds_lines.append("// Decorative stars/fireworks")
    ds_lines.append("firework_pts = [")
    fw_pts = []
    import random
    random.seed(42)
    for _ in range(40):
        fx = random.uniform(-10, 40)
        fy = random.uniform(-30, 10)
        fz = random.uniform(5, 15)
        fw_pts.append(f"Point.ByCoordinates({fx:.2f}, {fy:.2f}, {fz:.2f})")
    ds_lines.append(",\n".join(fw_pts))
    ds_lines.append("];")
    ds_lines.append("firework_spheres = Sphere.ByCenterPointRadius(firework_pts, 0.2);")
    
    return "\n".join(ds_lines)

if __name__ == "__main__":
    ds_code = generate_hny_designscript()
    
    instruction = {
        "nodes": [
            {
                "id": "hny_script",
                "name": "Number",
                "value": ds_code,
                "x": 0,
                "y": 0
            }
        ],
        "connectors": []
    }
    
    output_path = "d:/AI/An/AutodeskDynamo_MCP/DynamoScripts/happy_new_year.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"description": "Premium Happy New Year 2026 Geometry", "content": instruction}, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {output_path}")
