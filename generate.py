import json
from collections import defaultdict
from pathlib import Path
import requests

import os

SCRIPT_DIR = Path(__file__).parent.resolve()
README_FILE = SCRIPT_DIR / "README.md"
CONFIG_FILE = SCRIPT_DIR / "config.json"

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

GITHUB_USERNAME = config.get("github_username")
GITLAB_USERNAME = config.get("gitlab_username")
OPEN_SOURCE_ORGS = set(config.get("github_orgs", config.get("open_source_orgs", [])))
GITLAB_ORGS = set(config.get("gitlab_orgs", []))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")

def fetch_gitlab_mrs(username, group):
    page = 1
    results = []
    headers = {}
    if GITLAB_TOKEN:
        headers["PRIVATE-TOKEN"] = GITLAB_TOKEN

    while True:
        url = f"https://gitlab.com/api/v4/groups/{group}/merge_requests?author_username={username}&per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        results.extend(data)
        page += 1

    return results

def parse_gitlab_entry(entry):
    url = entry.get("web_url")
    if not url:
        return None
        
    parts = url.split("/")
    
    try:
        dash_idx = parts.index("-")
        repo = parts[dash_idx - 1]
    except ValueError:
        if len(parts) > 4:
            repo = parts[4]
        else:
            repo = "unknown"
            
    if len(parts) > 3:
        org = parts[3]
    else:
        return None
    
    if org not in GITLAB_ORGS:
        return None
        
    title = entry["title"]
    state = entry["state"]
    
    if state == "merged":
        status = "![Merged](https://img.shields.io/badge/Merged-purple)"
    elif state == "opened":
        status = "![Open](https://img.shields.io/badge/Open-green)"
    else:
        return None
        
    project_url = url.split("/-/")[0]
    repo_link = f"{project_url}/-/merge_requests/?sort=created_asc&state=merged&author_username={GITLAB_USERNAME}"
    
    return {
        "platform": "GitLab",
        "org": "GitLab",
        "repo": repo,
        "title": title,
        "status": status,
        "url": url,
        "repo_link": repo_link,
    }

def fetch_all_prs():
    page = 1
    results = []
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    while True:
        search_api = (
            f"https://api.github.com/search/issues?q=author:{GITHUB_USERNAME}+is:pr&per_page=30&page={page}"
        )

        response = requests.get(search_api, headers=headers)
        data = response.json()

        items = data.get("items", [])

        if not items:
            break

        results.extend(items)
        page += 1

    return results

def parse_entry(entry):
    url = entry["html_url"]
    parts = url.split("/")

    org = parts[3]
    repo = parts[4]

    # Pre-filter by org to only process relevant repositories
    if org not in OPEN_SOURCE_ORGS:
        return None

    title = entry["title"]

    pr_obj = entry.get("pull_request", {})
    if pr_obj.get("merged_at"):
        status = "![Merged](https://img.shields.io/badge/Merged-purple)"
    elif entry.get("state") == "open":
        status = "![Open](https://img.shields.io/badge/Open-green)"
    else:
        status = "Closed ❌"

    repo_link = f"https://github.com/{org}/{repo}/pulls?q=author%3A{GITHUB_USERNAME}"

    return {
        "platform": "GitHub",
        "org": org,
        "repo": repo,
        "title": title,
        "status": status,
        "url": url,
        "repo_link": repo_link,
    }


items = []

if GITHUB_USERNAME and OPEN_SOURCE_ORGS:
    all_prs = fetch_all_prs()
    print(f"Total PRs fetched from GitHub search API: {len(all_prs)}")
    for entry in all_prs:
        item = parse_entry(entry)
        if not item:
            continue
        if item["status"] == "Closed ❌":
            continue
        items.append(item)

if GITLAB_USERNAME and GITLAB_ORGS:
    for group in GITLAB_ORGS:
        mrs = fetch_gitlab_mrs(GITLAB_USERNAME, group)
        print(f"Total MRs fetched from GitLab group {group}: {len(mrs)}")
        for entry in mrs:
            item = parse_gitlab_entry(entry)
            if item:
                items.append(item)

orgs = defaultdict(list)
for item in items:
    orgs[item["org"]].append(item)

lines = ["# Open Source Contributions", ""]

for org, values in orgs.items():
    values.sort(key=lambda x: x["repo"].lower())
    lines.append(f"## {org} <!-- PRs: {len(values)} -->")
    lines.append("")
    lines.append("| Repo | PR Title | Status |")
    lines.append("|------|----------|--------|")

    prev_repo = None

    for v in values:
        if v["repo"] != prev_repo:
            repo_col = f"[{v['repo']}]({v['repo_link']})"
        else:
            repo_col = ""

        title = f"[{v['title']}]({v['url']})"

        lines.append(
            f"| {repo_col} | {title} | {v['status']} |"
        )

        prev_repo = v["repo"]

    lines.append("\n---\n")

Path(README_FILE).write_text("\n".join(lines))

print("README generated")
