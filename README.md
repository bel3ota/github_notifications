# GitHub → Discord Notifier

**Get every GitHub update in Discord: pushes, pull requests, issues, releases and GitHub Actions builds. Covers all your repos, private ones included, and you set it up once.**

[![CI](https://github.com/bel3ota/github-discord-notifier/actions/workflows/ci.yml/badge.svg)](https://github.com/bel3ota/github-discord-notifier/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white)](https://github.com/bel3ota/github-discord-notifier/pkgs/container/github-discord-notifier)

A small self-hosted tool that watches your GitHub account and posts what happens to a Discord channel. You don't need to set up a webhook on each repo or open any ports, and nothing needs `pip install`. It's one Python file.

```
⬆️ bel3ota pushed to main on bel3ota/krinov (diff)
> a1b2c3d fix login redirect
🏗️ Build started: CI on bel3ota/krinov `main` (run)
❌ Build failure: CI on bel3ota/krinov `main` (run)
🔀 bel3ota merged PR #12 Add dark mode on bel3ota/chat
🚀 bel3ota published release v1.2.0 on bel3ota/NetConfig
⭐ someone starred bel3ota/Pcaphunt
```

## Why this instead of Discord's built-in GitHub webhook?

| | This notifier | Discord's `/github` webhook |
|---|---|---|
| Setup | Once, for your whole account | Once **per repository** |
| New repos | Picked up automatically | You have to add them by hand |
| GitHub Actions: build started + finished | ✅ One line each | Depends on per-repo event settings |
| Runs behind NAT, at home, on a Raspberry Pi | ✅ No inbound ports needed | (nothing to host) |
| Covers repos you don't admin | ✅ Your own activity anywhere | ❌ Needs repo admin |
| Something to host | A tiny always-on process | Nothing |

## Features

- **Pushes**, with the branch, commit messages and a diff link
- **Pull requests:** opened, merged, closed, reviewed, commented
- **Issues** and comments
- **GitHub Actions builds:** started, then ✅ success / ❌ failure / ⚪ cancelled
- **Releases**, new branches and tags, deletions, **stars** and **forks**
- **Private repositories**, with a read-only token
- **Doesn't spam old history:** the first run records what already happened and only posts new events
- **Survives restarts:** progress is saved to disk, so nothing is posted twice or missed
- **Uses little of your API quota:** it sends conditional requests (ETags), so polls where nothing changed don't count against GitHub's rate limit
- **No dependencies:** only the Python standard library. Docker image for amd64, arm64 and armv7 (Raspberry Pi)

## Quick start

### 1. Get the two secrets

**Discord webhook:** open your channel's settings → **Integrations** → **Webhooks** → **New Webhook** → **Copy Webhook URL**.

**GitHub token:** [create a fine-grained token](https://github.com/settings/personal-access-tokens/new) with:
- Repository access: **All repositories** (or pick some)
- Permissions: **Actions: Read-only** and **Metadata: Read-only**

### 2. Configure

```bash
git clone https://github.com/bel3ota/github-discord-notifier
cd github-discord-notifier
cp .env.example .env   # then edit .env
```

### 3. Run it (pick one)

**Docker (recommended)**
```bash
docker compose up -d
docker compose logs -f
```

**Docker without cloning**
```bash
docker run -d --name github-discord --restart unless-stopped \
  -e GITHUB_USER=you -e GITHUB_TOKEN=github_pat_xxx \
  -e DISCORD_WEBHOOK=https://discord.com/api/webhooks/xxx/yyy \
  -v github-discord:/data ghcr.io/bel3ota/github-discord-notifier:latest
```

**Plain Python 3.9+** (anything: a VPS, your PC, a Raspberry Pi)
```bash
python3 notifier.py
```

**systemd service (Linux server)**
```bash
sudo mkdir -p /opt/github-discord-notifier
sudo cp notifier.py .env /opt/github-discord-notifier/
sudo chmod 600 /opt/github-discord-notifier/.env
sudo cp github-discord-notifier.service /etc/systemd/system/
sudo systemctl enable --now github-discord-notifier
journalctl -u github-discord-notifier -f
```

Push a commit to any repo, and it should show up in Discord within a minute or two.

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_USER` | ✅ | | Your GitHub username |
| `GITHUB_TOKEN` | ✅ | | Fine-grained token (see above) |
| `DISCORD_WEBHOOK` | | *(prints to stdout)* | Discord webhook URL. Leave it empty to try things out in the terminal |
| `INTERVAL` | | `60` | Seconds between polls |
| `BUILD_REPOS` | | `10` | How many of your most recently pushed repos to watch for builds (max 100) |
| `STATE_FILE` | | `state.json` | Where progress is saved |

You can set these as environment variables or in a `.env` file next to `notifier.py`. If a variable is set in both places, the environment variable wins.

## How it works

Every `INTERVAL` seconds it checks two things:
1. `GET /users/{user}/events`: your account's activity feed (pushes, PRs, issues, releases and more)
2. `GET /repos/{repo}/actions/runs` for your most recently pushed repos: build status

Each new item becomes one line in Discord. It never has to accept incoming connections, so it runs anywhere with internet access.

**Rate limits:** with the defaults it uses about 660 of your 5,000 requests per hour at most, and much less in practice because polls where nothing changed don't count.

## FAQ

**Why does a push take a few minutes to show up?**
GitHub's activity feed is delayed by 30 seconds to about 5 minutes; that comes from GitHub, not this tool. Build updates come within about one `INTERVAL`.

**Can I run it for several accounts or channels?**
Yes. Run one container or process per account, each with its own `.env` and state file.

**Does it need a Discord bot account?**
No. A channel webhook is enough, and it's simpler and safer.

**Is my token safe?**
It only needs read-only access, and it only ever goes to `api.github.com`. Keep `.env` out of git (it's already in `.gitignore`).

## Development

```bash
python3 test_notifier.py   # checks against live public GitHub data; set GITHUB_TOKEN to avoid rate limits
```

To support a new event type, add a branch in `fmt_event()`. PRs are welcome.

## License

[MIT](LICENSE). If this saves you time, a ⭐ helps other people find it.
