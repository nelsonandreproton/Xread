"""Fetch tweet content via fxtwitter public API (no auth required)."""

import logging
import re
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)

FXTWITTER_API = "https://api.fxtwitter.com/{username}/status/{tweet_id}"
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"
)


@dataclass
class TweetData:
    url: str
    tweet_id: str
    username: str
    author_name: str
    text: str


def parse_tweet_url(url: str) -> tuple[str, str]:
    """Return (username, tweet_id) from a Twitter/X URL. Raises ValueError if invalid."""
    match = URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(f"Not a valid Twitter/X URL: {url}")
    return match.group(1), match.group(2)


def _is_rate_limit(exc: Exception) -> bool:
    return "429" in str(exc)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(lambda exc: not _is_rate_limit(exc)),
    reraise=True,
)
def fetch_tweet(url: str) -> TweetData:
    """Fetch tweet data from fxtwitter API. Raises on failure."""
    username, tweet_id = parse_tweet_url(url)
    api_url = FXTWITTER_API.format(username=username, tweet_id=tweet_id)

    logger.debug("Fetching tweet %s via fxtwitter", tweet_id)
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()

    data = response.json()
    if data.get("code") != 200:
        raise RuntimeError(f"fxtwitter returned code {data.get('code')}: {data.get('message')}")

    tweet = data["tweet"]
    text = tweet.get("text") or tweet.get("raw_text", {}).get("text", "")
    if not text:
        raise RuntimeError(f"No text found in tweet {tweet_id}")

    return TweetData(
        url=url,
        tweet_id=tweet_id,
        username=username,
        author_name=tweet["author"]["name"],
        text=text,
    )
