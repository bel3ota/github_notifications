#!/usr/bin/env python3
"""Poll GitHub (account events + Actions runs) and post updates to a Discord webhook.

Stdlib only. Polling instead of webhooks, so it runs anywhere without open ports.
Config comes from the environment or a .env file next to this script (see .env.example).
"""
import json, os, sys, time, urllib.error, urllib.request

try:  # real environment variables win over .env
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")) as f:
        for line in f:
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
except OSError:
    pass

GH = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER = os.environ.get("GITHUB_USER", "")
HOOK = os.environ.get("DISCORD_WEBHOOK", "")
INTERVAL = int(os.environ.get("INTERVAL", "60"))
STATE = os.environ.get("STATE_FILE", "state.json")
BUILD_REPOS = int(os.environ.get("BUILD_REPOS", "10"))
UA = "github-discord-notifier"  # Discord's Cloudflare rejects urllib's default UA


def req(url, data=None, headers={}):
    r = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **headers})
    with urllib.request.urlopen(r, timeout=30) as resp:
        body = resp.read()
        return resp.headers, json.loads(body) if body else None


etags = {}  # path -> (etag, data); 304 responses don't count against the rate limit


def gh(path):
    h = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    if path in etags:
        h["If-None-Match"] = etags[path][0]
    try:
        hd, data = req(GH + path, headers=h)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return etags[path][1]
        raise
    etags[path] = (hd.get("ETag"), data)
    return data


def post(text):
    if not HOOK:
        return print(text, "\n")
    body = json.dumps({"content": text[:2000], "flags": 4, "allowed_mentions": {"parse": []}}).encode()
    while True:
        try:
            return req(HOOK, body, {"Content-Type": "application/json"})
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(float(json.loads(e.read()).get("retry_after", 1)))


def fmt_event(e):
    t, p, repo, who = e["type"], e["payload"], e["repo"]["name"], e["actor"]["login"]
    u = f"https://github.com/{repo}"
    r, a = f"[{repo}]({u})", p.get("action", "")
    if t == "PushEvent":
        branch = p.get("ref", "").removeprefix("refs/heads/")
        diff = f"{u}/compare/{p.get('before', '')[:12]}...{p.get('head', '')[:12]}"
        lines = [f"⬆️ **{who}** pushed to `{branch}` on {r} ([diff]({diff}))"]
        lines += [f"> `{c['sha'][:7]}` {c['message'].splitlines()[0]}" for c in p.get("commits", [])[:5]]
        return "\n".join(lines)
    if t in ("PullRequestEvent", "PullRequestReviewEvent", "PullRequestReviewCommentEvent"):
        pr = p.get("pull_request", {})
        n = p.get("number") or pr.get("number")
        if t == "PullRequestEvent" and a == "closed" and pr.get("merged"):
            a = "merged"
        if t == "PullRequestReviewEvent":
            a = f"reviewed ({p.get('review', {}).get('state', '')})"
        if t == "PullRequestReviewCommentEvent":
            a = "commented on"
        return f"🔀 **{who}** {a} PR [#{n} {pr.get('title', '')}]({pr.get('html_url', f'{u}/pull/{n}')}) on {r}"
    if t in ("IssuesEvent", "IssueCommentEvent"):
        i = p.get("issue", {})
        url = p.get("comment", {}).get("html_url") or i.get("html_url", u)
        verb = "commented on" if t == "IssueCommentEvent" else a
        return f"📝 **{who}** {verb} issue [#{i.get('number')} {i.get('title', '')}]({url}) on {r}"
    if t in ("CreateEvent", "DeleteEvent"):
        verb = "created" if t == "CreateEvent" else "deleted"
        ref = f" `{p['ref']}`" if p.get("ref") else ""
        return f"🌿 **{who}** {verb} {p.get('ref_type', '')}{ref} on {r}"
    if t == "ReleaseEvent":
        rel = p.get("release", {})
        return f"🚀 **{who}** {a} release [{rel.get('tag_name', '')}]({rel.get('html_url', u)}) on {r}"
    if t == "WatchEvent":
        return f"⭐ **{who}** starred {r}"
    if t == "ForkEvent":
        f = p.get("forkee", {}).get("full_name", "")
        return f"🍴 **{who}** forked {r} to [{f}](https://github.com/{f})"
    return f"🔔 **{who}** {t.removesuffix('Event')} {a} on {r}".replace("  ", " ")


def fmt_run(run, started):
    repo = run["repository"]["full_name"]
    head = f"**{run['name']}** on [{repo}](https://github.com/{repo}) `{run['head_branch']}`"
    link = f"([run]({run['html_url']}))"
    if started:
        return f"🏗️ Build started: {head} {link}"
    icon = {"success": "✅", "failure": "❌", "cancelled": "⚪"}.get(run["conclusion"], "⚠️")
    return f"{icon} Build {run['conclusion']}: {head} {link}"


def poll(state, quiet):
    for e in reversed(gh(f"/users/{USER}/events?per_page=50")):  # API returns newest first
        if e["id"] not in state["events"]:
            quiet or post(fmt_event(e))
            state["events"].append(e["id"])
    state["events"] = state["events"][-500:]

    # each repo costs one API call per poll; 10 repos @ 60s is ~660 of the 5000/h limit
    for repo in gh(f"/user/repos?sort=pushed&per_page={BUILD_REPOS}"):
        runs = gh(f"/repos/{repo['full_name']}/actions/runs?per_page=5")["workflow_runs"]
        for run in reversed(runs):
            key, status = f"{run['id']}/{run['run_attempt']}", run["status"]
            prev = state["runs"].get(key)
            if prev == status or prev == "completed":
                continue
            if not quiet and (status == "completed" or prev is None):
                post(fmt_run(run, status != "completed"))
            state["runs"][key] = status
    state["runs"] = dict(list(state["runs"].items())[-1000:])


def main():
    if not (TOKEN and USER):
        sys.exit("GITHUB_TOKEN and GITHUB_USER are required")
    try:
        with open(STATE) as f:
            state, quiet = json.load(f), False
    except FileNotFoundError:
        state, quiet = {"events": [], "runs": {}}, True  # first run: record history, don't spam it
    while True:
        try:
            poll(state, quiet)
            quiet = False
            with open(STATE + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(STATE + ".tmp", STATE)
        except Exception as ex:
            print("poll failed:", repr(ex), file=sys.stderr, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
