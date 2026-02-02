import os
import math
import random
import requests
import datetime

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
USERNAME = os.getenv("GITHUB_ACTOR")  # Automatically gets the user who triggered the action
OUTPUT_FILE = "github_tree.svg"
MAX_REPOS = 8  # Limit branches to keep it clean

# --- SVG HELPER CLASS (No external image libraries needed) ---
class SVG:
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.elements = []
    
    def add_rect(self, x, y, w, h, fill):
        self.elements.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" />')

    def add_line(self, x1, y1, x2, y2, stroke, width):
        self.elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" />')

    def add_circle(self, cx, cy, r, fill, opacity=1.0):
        self.elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" fill-opacity="{opacity}" />')

    def add_text(self, x, y, text, size, color):
        self.elements.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{color}" text-anchor="middle">{text}</text>')

    def save(self, filename):
        svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" viewBox="0 0 {self.width} {self.height}">'
        svg_content += f'<rect width="100%" height="100%" fill="#f0f4f8"/>' # Background
        svg_content += "\n".join(self.elements)
        svg_content += '</svg>'
        with open(filename, "w") as f:
            f.write(svg_content)

# --- GITHUB API DATA FETCHER ---
def get_github_data():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    
    # GraphQL Query for efficient data fetching
    query = """
    query($login: String!) {
      user(login: $login) {
        createdAt
        repositories(first: 20, ownerAffiliations: OWNER, orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            name
            stargazerCount
            defaultBranchRef {
              target {
                ... on Commit {
                  history {
                    totalCount
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    
    response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': {'login': USERNAME}}, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"API Query Failed: {response.text}")
        
    data = response.json()
    if 'errors' in data:
         # Fallback for empty/error states (prevents crash on first run)
        return {"years_active": 1, "repos": []}

    user = data['data']['user']
    created_year = int(user['createdAt'][:4])
    current_year = datetime.datetime.now().year
    years_active = max(1, current_year - created_year + 1)
    
    repos = []
    for node in user['repositories']['nodes']:
        commits = node['defaultBranchRef']['target']['history']['totalCount'] if node['defaultBranchRef'] else 0
        repos.append({
            "name": node['name'],
            "stars": node['stargazerCount'],
            "commits": commits
        })
        
    return {"years_active": years_active, "repos": repos[:MAX_REPOS]}

# --- DRAWING ALGORITHM ---
def draw_tree(data):
    svg = SVG(800, 600)
    
    # 1. Draw Ground
    svg.add_rect(0, 550, 800, 50, "#3e2723") # Dark soil
    svg.add_rect(0, 540, 800, 10, "#4caf50") # Grass
    
    # 2. Draw Trunk (Thickness = Years Active)
    start_x = 400
    start_y = 550
    trunk_height = 150
    trunk_width = 20 + (data['years_active'] * 5)
    
    # Draw trunk as a thick line
    svg.add_line(start_x, start_y, start_x, start_y - trunk_height, "#5d4037", trunk_width)
    
    # 3. Draw Branches (Repos)
    branch_start_x = start_x
    branch_start_y = start_y - trunk_height
    
    angle_step = 160 / (len(data['repos']) + 1) # Spread branches across 160 degrees
    current_angle = 190 # Start from left-ish
    
    for repo in data['repos']:
        # Branch Properties
        branch_len = 120 + random.randint(0, 40)
        rad = math.radians(current_angle)
        
        end_x = branch_start_x + branch_len * math.cos(rad)
        end_y = branch_start_y + branch_len * math.sin(rad)
        
        # Draw Branch
        svg.add_line(branch_start_x, branch_start_y, end_x, end_y, "#795548", 8)
        
        # Draw Leaves (Commits) along the branch
        # Scale: 1 leaf = ~10 commits (capped at 20 leaves per branch to avoid clutter)
        num_leaves = min(20, max(3, repo['commits'] // 10))
        
        for _ in range(num_leaves):
            # Random position along the branch
            t = random.uniform(0.3, 1.0) # Don't put leaves too close to trunk
            lx = branch_start_x + (end_x - branch_start_x) * t
            ly = branch_start_y + (end_y - branch_start_y) * t
            
            # Jitter
            lx += random.uniform(-15, 15)
            ly += random.uniform(-15, 15)
            
            # Leaf color (vary slightly)
            g_val = random.randint(150, 255)
            svg.add_circle(lx, ly, random.randint(4, 8), f"rgb(50, {g_val}, 50)", 0.8)

        # Draw Flowers (Stars) at the tip of the branch
        if repo['stars'] > 0:
            svg.add_circle(end_x, end_y, 10 + (repo['stars'] * 2), "#ffeb3b") # Yellow flower
            svg.add_circle(end_x, end_y, 5, "#ff9800") # Orange center
            
        current_angle -= angle_step # Rotate for next branch

    # 4. Text Info
    svg.add_text(400, 580, f"Grown over {data['years_active']} years", 16, "#ffffff")
    
    svg.save(OUTPUT_FILE)
    print(f"Tree generated: {OUTPUT_FILE}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        user_data = get_github_data()
        draw_tree(user_data)
    except Exception as e:
        print(f"Error: {e}")
        # Generate a dummy tree if API fails so workflow doesn't crash
        dummy_data = {"years_active": 1, "repos": [{"name": "Error", "stars": 0, "commits": 10}]}
        draw_tree(dummy_data)
