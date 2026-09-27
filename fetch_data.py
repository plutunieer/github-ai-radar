"""Fetch new AI repos from GitHub (created in the last 90 days) and build data.js for radar.html.

Needs the GitHub CLI (`gh`), logged in. Takes a few minutes because of the search rate limit.
"""
import collections
import datetime as dt
import json
import statistics
import subprocess
import time

SINCE = (dt.date.today() - dt.timedelta(days=90)).isoformat()
MIN_STARS = 15
PAGES_PER_TOPIC = 2  # 100 repos per page -> top 200 per topic, sorted by stars

# Each category is a group of GitHub topics. Change these to map any other field.
CATS = {
    "agents": ["ai-agents", "agents", "ai-agent", "agentic-ai", "multi-agent"],
    "coding": ["claude-code", "mcp", "code-generation", "coding-agent", "vibe-coding"],
    "image/video": ["image-generation", "text-to-video", "stable-diffusion", "video-generation", "comfyui"],
    "rag": ["rag", "retrieval-augmented-generation", "vector-database", "knowledge-graph"],
    "voice": ["tts", "text-to-speech", "speech-to-text", "voice-assistant", "voice-ai"],
    "local models": ["ollama", "local-llm", "llama", "llamacpp", "fine-tuning"],
}


def search(query, page):
    for attempt in range(3):
        out = subprocess.run(["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={query}", "-f", "sort=stars",
                              "-f", "per_page=100", "-f", f"page={page}"], capture_output=True, text=True)
        if not out.returncode:
            return json.loads(out.stdout).get("items", [])
        time.sleep(30)  # usually the search rate limit
    raise SystemExit(f"GitHub search failed for {query!r} page {page}: {out.stderr.strip()[-300:]}")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    repos = {}
    for cat, topics in CATS.items():
        for topic in topics:
            for page in range(1, PAGES_PER_TOPIC + 1):
                items = search(f"topic:{topic} created:>{SINCE} stars:>{MIN_STARS}", page)
                for r in items:
                    if r["full_name"] in repos:
                        continue  # first category wins
                    age = max(1, (now - dt.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))).days)
                    repos[r["full_name"]] = {"name": r["full_name"], "cat": cat, "stars": r["stargazers_count"],
                                             "age": age, "per_day": round(r["stargazers_count"] / age, 1),
                                             "lang": r["language"] or "other", "desc": (r["description"] or "")[:90]}
                time.sleep(2.2)
                if len(items) < 100:
                    break

    rows = sorted(repos.values(), key=lambda r: -r["per_day"])
    json.dump({"since": SINCE, "fetched": now.isoformat(timespec="minutes"), "repos": rows},
              open("data.json", "w"), ensure_ascii=False, indent=1)

    cats = list(CATS)
    total = sum(r["stars"] for r in rows)
    summary = {
        "n": len(rows), "stars": total, "since": SINCE, "fetched": now.isoformat(timespec="minutes"),
        "cat": {c: {"n": sum(r["cat"] == c for r in rows), "stars": sum(r["stars"] for r in rows if r["cat"] == c)} for c in cats},
        "breakouts": sum(r["per_day"] >= 100 for r in rows),
        "breakouts_agents": sum(r["per_day"] >= 100 and r["cat"] == cats[0] for r in rows),
        "top": [{"name": r["name"], "per_day": r["per_day"], "cat": r["cat"]} for r in rows[:5]],
        "lang": collections.Counter(r["lang"] for r in rows).most_common(5),
    }
    topcat = {}
    for c in cats:
        x = [r for r in rows if r["cat"] == c]
        topcat[c] = {"median": statistics.median(r["per_day"] for r in x) if x else 0,
                     "top": [{"name": r["name"], "per_day": r["per_day"], "stars": r["stars"], "desc": r["desc"]} for r in x[:3]]}
    with open("data.js", "w") as f:
        f.write("window.REPOS=" + json.dumps([[r["name"], cats.index(r["cat"]), r["per_day"], r["stars"]] for r in rows]) + ";\n")
        f.write("window.SUM=" + json.dumps(summary) + ";\n")
        f.write("window.TOPCAT=" + json.dumps(topcat) + ";\n")
    print(f"{len(rows)} repos, {total:,} stars -> data.json, data.js")


if __name__ == "__main__":
    main()
