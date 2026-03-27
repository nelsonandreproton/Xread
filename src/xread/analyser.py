"""Analyse tweet content using Groq, personalised to the user's Obsidian context."""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .fetcher import TweetData

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """\
You are a personal knowledge assistant for a software developer named Nelson.
You help him extract actionable insights from Twitter/X posts, tailored specifically
to his current projects, tech stack, and goals.

Nelson's profile and context will be provided. Your job is to analyse a tweet and return:
1. A concise 1-line title (max 80 chars) that captures the core idea
2. Exactly 5 takeaways, personalised to Nelson's scenario
   - Each takeaway must be actionable or insightful for his specific situation
   - At least ONE takeaway must challenge or question his current assumptions or approach
   - Mark that one with the prefix [Challenge]
3. 3–5 relevant tags (lowercase, no #, e.g. "ai", "claude-code", "productivity")

Respond ONLY with valid JSON in this exact format:
{
  "title": "...",
  "takeaways": ["...", "...", "...", "...", "..."],
  "tags": ["...", "..."]
}
"""


@dataclass
class ReadInsight:
    title: str
    takeaways: list[str]
    tags: list[str]


def _load_context(vault_path: str) -> str:
    """Load me.md and system.md from the vault for personalisation context."""
    vault = Path(vault_path)
    parts = []
    for filename in ("me.md", "system.md"):
        filepath = vault / filename
        if filepath.exists():
            parts.append(f"=== {filename} ===\n{filepath.read_text(encoding='utf-8')}")
        else:
            logger.warning("Vault context file not found: %s", filepath)
    return "\n\n".join(parts)


def _is_rate_limit(exc: Exception) -> bool:
    return "429" in str(exc)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception(lambda exc: not _is_rate_limit(exc)),
    reraise=True,
)
def analyse_tweet(tweet: TweetData, vault_path: str | None = None) -> ReadInsight:
    """Generate title, takeaways, and tags for a tweet using Groq."""
    api_key = os.environ["GROQ_API_KEY"]
    vault_path = vault_path or os.environ["OBSIDIAN_VAULT_PATH"]

    context = _load_context(vault_path)
    client = Groq(api_key=api_key)

    user_message = f"""\
Nelson's personal context:
{context}

---
Tweet by @{tweet.username} ({tweet.author_name}):
{tweet.text}

Source: {tweet.url}
"""

    logger.debug("Calling Groq for tweet %s", tweet.tweet_id)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Groq returned invalid JSON: {raw[:200]}") from exc

    title = data.get("title", "").strip()
    takeaways = data.get("takeaways", [])
    tags = data.get("tags", [])

    if not title:
        raise RuntimeError("Groq returned empty title")
    if len(takeaways) != 5:
        raise RuntimeError(f"Expected 5 takeaways, got {len(takeaways)}")

    return ReadInsight(title=title, takeaways=takeaways, tags=tags)
