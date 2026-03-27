"""Tests for xread.fetcher module."""

import pytest
from unittest.mock import patch, MagicMock

from xread.fetcher import fetch_tweet, parse_tweet_url, TweetData


class TestParseTweetUrl:
    def test_parse_x_com_url(self):
        username, tweet_id = parse_tweet_url("https://x.com/vishisinghal_/status/2037534716191297882")
        assert username == "vishisinghal_"
        assert tweet_id == "2037534716191297882"

    def test_parse_twitter_com_url(self):
        username, tweet_id = parse_tweet_url("https://twitter.com/user/status/123456")
        assert username == "user"
        assert tweet_id == "123456"

    def test_parse_www_prefix(self):
        username, tweet_id = parse_tweet_url("https://www.x.com/someone/status/999")
        assert username == "someone"
        assert tweet_id == "999"

    def test_parse_url_with_trailing_whitespace(self):
        username, tweet_id = parse_tweet_url("  https://x.com/user/status/123  ")
        assert username == "user"
        assert tweet_id == "123"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Not a valid Twitter/X URL"):
            parse_tweet_url("https://example.com/foo")

    def test_empty_url_raises(self):
        with pytest.raises(ValueError):
            parse_tweet_url("")


class TestFetchTweet:
    def _make_response(self, text="Tweet content here", author="Test Author", username="testuser"):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "code": 200,
            "message": "OK",
            "tweet": {
                "url": f"https://x.com/{username}/status/123",
                "id": "123",
                "text": text,
                "author": {"name": author, "screen_name": username},
            },
        }
        mock.raise_for_status = MagicMock()
        return mock

    @patch("xread.fetcher.requests.get")
    def test_fetch_returns_tweet_data(self, mock_get):
        mock_get.return_value = self._make_response(
            text="Hello world", author="Alice", username="alice"
        )
        result = fetch_tweet("https://x.com/alice/status/123")
        assert isinstance(result, TweetData)
        assert result.text == "Hello world"
        assert result.author_name == "Alice"
        assert result.username == "alice"
        assert result.tweet_id == "123"

    @patch("xread.fetcher.requests.get")
    def test_fetch_raises_on_api_error_code(self, mock_get):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {"code": 404, "message": "Not Found"}
        mock_get.return_value = mock

        with pytest.raises(RuntimeError, match="fxtwitter returned code 404"):
            fetch_tweet("https://x.com/user/status/123")

    @patch("xread.fetcher.requests.get")
    def test_fetch_raises_on_empty_text(self, mock_get):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = {
            "code": 200,
            "message": "OK",
            "tweet": {
                "url": "https://x.com/user/status/123",
                "id": "123",
                "text": "",
                "raw_text": {"text": ""},
                "author": {"name": "User", "screen_name": "user"},
            },
        }
        mock_get.return_value = mock

        with pytest.raises(RuntimeError, match="No text found"):
            fetch_tweet("https://x.com/user/status/123")

    def test_invalid_url_raises_before_request(self):
        with pytest.raises(ValueError):
            fetch_tweet("https://nottwitter.com/foo")
