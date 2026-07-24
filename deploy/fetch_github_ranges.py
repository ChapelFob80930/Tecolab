import requests
import json

resp = requests.get("https://api.github.com/meta")
data = resp.json()
actions_ranges = data["actions"]

print(f"Total ranges: {len(actions_ranges)}")
for cidr in actions_ranges[:5]:  # CIDR stands for Classless Inter-Domain Routing which is a method for allocating IP addresses and routing internet traffic.
    # It replaces the older, rigid "class-based" addressing system by using a flexible network prefix (written as a slash and a number, e.g., /24) to dictate
    # exactly how many IP addresses a network contains
    print(cidr)

with open("github_actions_ranges.json", "w") as f:
    json.dump(actions_ranges, f, indent = 2)