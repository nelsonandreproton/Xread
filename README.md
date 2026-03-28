# xread

Python library that fetches a Twitter/X post, analyses it with Groq LLM, and writes a markdown note to an Obsidian vault — then pushes it to GitHub via the Contents API.

Used by [GarminBot](https://github.com/nelsonandre/GarminBot) via the `/xread` Telegram command.

## What it does

1. **Fetch** — retrieves tweet text via the [fxtwitter](https://github.com/FixTweet/FxTwitter) public API (no Twitter auth required).
2. **Analyse** — sends the tweet to Groq (`llama-3.3-70b-versatile`) with your Obsidian personal context (`me.md`, `system.md`) and returns a title, 5 personalised takeaways, and tags.
3. **Write** — creates a dated markdown note under `<vault>/reads/` with YAML front-matter.
4. **Push** — commits the note to GitHub via the Contents API (no `git push`, works in containers).

## Installation

```bash
pip install git+https://github.com/nelsonandre/xread.git
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key |
| `OBSIDIAN_VAULT_PATH` | Yes | Absolute path to Obsidian vault (or a subdirectory of the git repo) |
| `GITHUB_TOKEN` | No | Personal access token with `repo` scope — skips push if absent |

## Usage

```python
from xread.fetcher import fetch_tweet
from xread.analyser import analyse_tweet
from xread.vault_writer import write_to_vault

tweet = fetch_tweet("https://x.com/user/status/123456789")
insight = analyse_tweet(tweet)
filename = write_to_vault(tweet, insight)
print(filename)  # e.g. 2025-03-27-my-note-title.md
```

## GitHub push behaviour

`vault_writer` uses the **GitHub Contents API** (`PUT /repos/{owner}/{repo}/contents/{path}`) instead of `git push`. This is more reliable in containerised environments where SSH keys and git identity are not available.

- The git repository root is auto-detected from `vault_path` using `git rev-parse --show-toplevel`, so `vault_path` can be a subdirectory of the repo.
- The `origin` remote URL is read from git to determine the `owner/repo` slug.
- The committer identity (`GarminBot <garminbot@localhost>`) is set via the API request — no `git config` needed.
- If `GITHUB_TOKEN` is not set, the note is still written locally and the push is skipped with a warning.

## Note format

```markdown
---
source: https://x.com/user/status/123456789
author: "@username"
date: 2025-03-27
tags: ["ai", "productivity", "claude-code"]
---

# Note title

## Takeaways

1. First takeaway
2. Second takeaway
3. [Challenge] A takeaway that questions your current approach
4. Fourth takeaway
5. Fifth takeaway
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
