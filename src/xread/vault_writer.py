"""Write a Read note to the Obsidian vault and push to GitHub."""

import logging
import os
import re
import subprocess
from datetime import datetime, UTC
from pathlib import Path

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


def write_to_vault(
    tweet: TweetData,
    insight: ReadInsight,
    vault_path: str | None = None,
) -> str:
    """Write note to reads/ folder, commit and push. Returns the note filename."""
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

    git_root = _git_root(vault_path)
    relative_path = str(note_path.relative_to(git_root))

    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token:
        _git(["config", "http.extraheader", f"Authorization: Bearer {github_token}"], cwd=git_root)

    _git(["add", relative_path], cwd=git_root)
    _git(
        [
            "-c", "user.email=garminbot@localhost",
            "-c", "user.name=GarminBot",
            "commit", "-m", f"xread: {insight.title[:60]}",
        ],
        cwd=git_root,
    )
    _git(["push"], cwd=git_root)

    logger.info("Pushed note to GitHub: %s", filename)
    return filename
