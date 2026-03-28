"""Write a Read note to the Obsidian vault and push to GitHub via API."""

import base64
import logging
import os
import re
import subprocess
from datetime import datetime, UTC
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json

from .fetcher import TweetData
from .analyser import ReadInsight

logger = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    """Convert title to a filename-safe slug."""
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60]


def _render_note(tweet: TweetData, insight: ReadInsight, date_str: str) -> str:
    """Render the markdown note content."""
    tags_yaml = ", ".join(f'"{t}"' for t in insight.tags)
    takeaways_md = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(insight.takeaways))

    return f"""\
---
source: {tweet.url}
author: "@{tweet.username}"
date: {date_str}
tags: [{tags_yaml}]
---

# {insight.title}

## Takeaways

{takeaways_md}
"""


def _git(args: list[str], cwd: str) -> None:
    """Run a git command. Raises on failure."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")


def _git_root(path: str) -> str:
    """Return the git repository root for the given path."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return path


def _github_api_push(token: str, repo_slug: str, file_path: str, content: str, commit_message: str) -> None:
    """Create or update a file in a GitHub repo via the Contents API."""
    url = f"https://api.github.com/repos/{repo_slug}/contents/{file_path}"
    encoded = base64.b64encode(content.encode()).decode()

    # Check if file already exists (need its SHA to update)
    req = Request(url, headers={"Authorization": f"token {token}", "User-Agent": "GarminBot"})
    sha = None
    try:
        with urlopen(req) as resp:
            sha = json.loads(resp.read())["sha"]
    except HTTPError:
        pass  # File doesn't exist yet — create it

    payload: dict = {"message": commit_message, "content": encoded, "committer": {"name": "GarminBot", "email": "garminbot@localhost"}}
    if sha:
        payload["sha"] = sha

    put_req = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"token {token}", "Content-Type": "application/json", "User-Agent": "GarminBot"},
        method="PUT",
    )
    with urlopen(put_req) as resp:
        result = json.loads(resp.read())
    logger.info("GitHub API push: %s", result.get("commit", {}).get("sha", "?"))


def _parse_github_repo(remote_url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub remote URL."""
    m = re.search(r"github\.com[:/](.+?/[^/]+?)(?:\.git)?$", remote_url)
    return m.group(1) if m else None


def write_to_vault(
    tweet: TweetData,
    insight: ReadInsight,
    vault_path: str | None = None,
) -> str:
    """Write note to reads/ folder and push to GitHub. Returns the note filename."""
    vault_path = vault_path or os.environ["OBSIDIAN_VAULT_PATH"]
    vault = Path(vault_path)
    reads_dir = vault / "reads"
    reads_dir.mkdir(exist_ok=True)

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = _slugify(insight.title)
    filename = f"{date_str}-{slug}.md"
    note_path = reads_dir / filename

    note_content = _render_note(tweet, insight, date_str)
    note_path.write_text(note_content, encoding="utf-8")
    logger.info("Note written: %s", note_path)

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not github_token:
        logger.warning("GITHUB_TOKEN not set — skipping GitHub push")
        return filename

    git_root = _git_root(vault_path)
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=git_root, capture_output=True, text=True,
    )
    remote_url = result.stdout.strip()
    repo_slug = _parse_github_repo(remote_url)

    if not repo_slug:
        logger.warning("Could not parse GitHub repo from remote: %s — skipping push", remote_url)
        return filename

    relative_path = str(note_path.relative_to(git_root)).replace("\\", "/")
    _github_api_push(
        token=github_token,
        repo_slug=repo_slug,
        file_path=relative_path,
        content=note_content,
        commit_message=f"xread: {insight.title[:60]}",
    )

    return filename
