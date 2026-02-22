
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm

# 設定中文字型
font_path = r'C:\Windows\Fonts\msjh.ttc'
prop = fm.FontProperties(fname=font_path)

# 圖表設定
fig, ax = plt.subplots(figsize=(16, 9))
ax.set_facecolor('#1e1e1e')  # 深色背景
fig.patch.set_facecolor('#1e1e1e')
ax.axis('off')

# 定義方塊和文字
boxes = []
texts = []

# 輸入 (Inputs)
inputs = [
    "輸入 (Inputs)",
    "1. 選取房間 (Select Room)",
    "2. 選取計算元素 (Select Elements)",
    "3. 選取窗戶/帷幕 (Select Windows)",
    "4. 選取障礙物 (Select Obstacles)",
    "5. 設定檢視點 (X, Y)"
]

# 處理 (Process)
process = [
    "處理 (Process)",
    "1. 計算房間幾何中心",
    "2. 產生視線向量 (Python Script)",
    "3. 檢測障礙物遮擋",
    "4. 顏色映射計算 (GeometryColor)"
]

# 輸出 (Outputs)
outputs = [
    "輸出 (Outputs)",
    "1. 窗外視野分數 (View Score)",
    "2. 到窗戶的距離 (Distance to Window)",
    "3. 與窗戶的平均角度 (Average Angle)",
    "4. 幾何視覺化顯示"
]

def draw_section(x, color, title, items):
    # 標題框
    rect = patches.FancyBboxPatch((x, 0.8), 0.25, 0.1, boxstyle="round,pad=0.02", 
                                  linewidth=2, edgecolor=color, facecolor=color, alpha=0.3)
    ax.add_patch(rect)
    ax.text(x + 0.125, 0.85, title, ha='center', va='center', fontsize=20, color='white', fontproperties=prop, weight='bold')
    
    # 內容框
    for i, item in enumerate(items):
        y = 0.7 - (i * 0.12)
        item_rect = patches.FancyBboxPatch((x, y), 0.25, 0.08, boxstyle="round,pad=0.02", 
                                      linewidth=1, edgecolor=color, facecolor='#2d2d2d')
        ax.add_patch(item_rect)
        ax.text(x + 0.125, y + 0.04, item, ha='center', va='center', fontsize=12, color='white', fontproperties=prop)

# 繪製三個區塊
draw_section(0.05, '#00bcd4', "輸入 (Inputs)", inputs[1:])
draw_section(0.375, '#ffeb3b', "處理 (Process)", process[1:])
draw_section(0.7, '#e91e63', "輸出 (Outputs)", outputs[1:])

# 繪製箭頭
arrow_style = dict(arrowstyle="->", color="white", lw=2, mutation_scale=20)
ax.annotate("", xy=(0.365, 0.5), xytext=(0.31, 0.5), arrowprops=arrow_style)
ax.annotate("", xy=(0.69, 0.5), xytext=(0.635, 0.5), arrowprops=arrow_style)

# 標題
plt.title("最大化窗外視野 (Maximize Window View) - 流程說明圖", color='white', fontsize=24, pad=30, fontproperties=prop)

# 儲存
output_file = "image/maximize_view_flowchart.png"
plt.tight_layout()
plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
print(f"Flowchart saved to {output_file}")
