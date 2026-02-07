import os
import math
import random
import requests
import datetime

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
USERNAME = os.getenv("GITHUB_ACTOR")
OUTPUT_FILE = "github_tree.svg"
MAX_REPOS = 6  # Fewer, higher quality branches

# --- SVG HELPER CLASS ---
class SVG:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.elements = []
        # Add a nice gradient sky background
        self.defs = """
        <defs>
            <linearGradient id="sky" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#e0f7fa;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#ffffff;stop-opacity:1" />
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
        </defs>
        """

    def add_rect(self, x, y, w, h, fill):
        self.elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" />')

    def add_path(self, d, stroke, width, fill="none", opacity=1.0):
        # Using paths allows for curves (organic branches)
        self.elements.append(f'<path d="{d}" stroke="{stroke}" stroke-width="{width}" fill="{fill}" stroke-linecap="round" stroke-opacity="{opacity}" />')

    def add_circle(self, cx, cy, r, fill, opacity=0.8):
        self.elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="{opacity}" />')

    def add_text(self, x, y, text, size, color):
        self.elements.append(f'<text x="{x}" y="{y}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="{size}" fill="{color}" text-anchor="middle" font-weight="bold">{text}</text>')

    def save(self, filename):
        svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">'
        svg_content += self.defs
        svg_content += f'<rect width="100%" height="100%" fill="url(#sky)"/>' 
        svg_content += "\n".join(self.elements)
        svg_content += '</svg>'
        with open(filename, "w") as f:
            f.write(svg_content)

# --- MATH HELPERS FOR CURVES ---
def get_endpoint(x, y, length, angle_deg):
    rad = math.radians(angle_deg)
    return x + length * math.cos(rad), y + length * math.sin(rad)

# --- GITHUB DATA FETCHER (Unchanged) ---
def get_github_data():
    if not GITHUB_TOKEN:
        # Mock data for local testing if no token
        return {
            "years_active": 3, 
            "repos": [
                {"name": "Project-A", "stars": 12, "commits": 150},
                {"name": "Project-B", "stars": 5, "commits": 80},
                {"name": "Project-C", "stars": 20, "commits": 300},
                {"name": "Project-D", "stars": 2, "commits": 40},
                {"name": "Project-E", "stars": 0, "commits": 20},
            ]
        }

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    query = """
    query($login: String!) {
      user(login: $login) {
        createdAt
        repositories(first: 20, ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            name
            stargazerCount
            defaultBranchRef { target { ... on Commit { history { totalCount } } } }
          }
        }
      }
    }
    """
    try:
        response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': {'login': USERNAME}}, headers=headers)
        data = response.json()
        user = data['data']['user']
        created_year = int(user['createdAt'][:4])
        years_active = max(1, datetime.datetime.now().year - created_year + 1)
        repos = []
        for node in user['repositories']['nodes']:
            commits = node['defaultBranchRef']['target']['history']['totalCount'] if node['defaultBranchRef'] else 0
            if commits > 0: # Only show active repos
                repos.append({"name": node['name'], "stars": node['stargazerCount'], "commits": commits})
        return {"years_active": years_active, "repos": repos[:MAX_REPOS]}
    except:
        return {"years_active": 1, "repos": []}

# --- IMPROVED DRAWING ALGORITHM ---
def draw_tree(data):
    svg = SVG(800, 600)
    
    # 1. Ground (More stylistic)
    svg.add_path("M0,550 Q400,530 800,550 L800,600 L0,600 Z", "#4e342e", 0, "#5d4037")
    svg.add_path("M0,550 Q400,530 800,550", "none", 0, "#76ff03", 0.1) # Grass hint

    # 2. Main Trunk
    start_x, start_y = 400, 550
    trunk_len = 160
    
    # Curved Trunk: Using Quadratic Bezier (Q) for a natural bend
    # Format: M start_x start_y Q control_x control_y end_x end_y
    # We bend the trunk slightly based on random wind
    bend = random.randint(-30, 30)
    trunk_end_x = start_x + bend
    trunk_end_y = start_y - trunk_len
    
    ctrl_x = start_x + (bend / 2) # Control point for curve
    ctrl_y = start_y - (trunk_len / 2)

    # Draw Trunk (Thick path)
    trunk_path = f"M{start_x},{start_y} Q{ctrl_x},{ctrl_y} {trunk_end_x},{trunk_end_y}"
    svg.add_path(trunk_path, "#4e342e", 25 + (data['years_active'] * 2)) # Thickness based on age
    
    # 3. Branches (Repositories)
    # We attach branches along the top half of the trunk, not all at one point
    repos = data['repos']
    total_commits = sum(r['commits'] for r in repos) if repos else 1
    
    current_y = trunk_end_y + 40 # Start attaching branches slightly below the top
    
    # Sort repos by size so big branches are lower, small ones higher
    repos.sort(key=lambda x: x['commits'], reverse=True)

    for i, repo in enumerate(repos):
        # Determine branch side (alternate left/right)
        is_right = i % 2 == 0
        direction = 1 if is_right else -1
        
        # Branch properties
        branch_len = 100 + (repo['commits'] / total_commits) * 150 # Proportional length
        branch_len = min(branch_len, 250) # Cap max length
        
        angle_base = -45 if is_right else -135 # Up-Right or Up-Left
        angle = angle_base + random.randint(-20, 20)
        
        # Calculate Branch Curve
        bx, by = get_endpoint(trunk_end_x, current_y, branch_len, angle)
        
        # Curve control point (makes the branch sag or bow up)
        b_ctrl_x = trunk_end_x + (branch_len/2 * direction)
        b_ctrl_y = current_y - 20 
        
        svg.add_path(f"M{trunk_end_x},{current_y} Q{b_ctrl_x},{b_ctrl_y} {bx},{by}", "#5d4037", 8)
        
        # 4. Leaves (Commits) - Clustered Cloud
        # Instead of random dots, draw a "Cloud" of circles at the end of the branch
        cluster_size = min(40, max(10, repo['commits'] // 5))
        
        for _ in range(int(cluster_size)):
            # Randomize position around branch tip
            lx = bx + random.uniform(-35, 35)
            ly = by + random.uniform(-35, 35)
            
            # Varied Green Colors
            colors = ["#2e7d32", "#43a047", "#66bb6a", "#a5d6a7"] # Dark to light green
            leaf_color = random.choice(colors)
            leaf_size = random.randint(8, 16)
            
            svg.add_circle(lx, ly, leaf_size, leaf_color, 0.7)

        # 5. Flowers (Stars) - Glowing
        if repo['stars'] > 0:
            star_count = min(5, repo['stars']) # Don't overpopulate
            for _ in range(star_count):
                sx = bx + random.uniform(-20, 20)
                sy = by + random.uniform(-20, 20)
                svg.add_circle(sx, sy, 5, "#ffeb3b", 1.0) # Core
                svg.add_circle(sx, sy, 9, "#ffeb3b", 0.3) # Glow
                
        # Move up the trunk for the next branch
        current_y -= 15

    # Footer
    svg.add_text(400, 580, f"@{USERNAME}'s Contribution Garden", 20, "#3e2723")
    svg.add_text(400, 595, f"Grown over {data['years_active']} years", 14, "#5d4037")

    svg.save(OUTPUT_FILE)
    print(f"Tree generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    draw_tree(get_github_data())
