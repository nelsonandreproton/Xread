"""Tests for xread.analyser module."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from xread.fetcher import TweetData
from xread.analyser import analyse_tweet, ReadInsight, _load_context


class TestLoadContext:
    def test_loads_both_files(self, tmp_path):
        (tmp_path / "me.md").write_text("# Me\nNelson, developer.", encoding="utf-8")
        (tmp_path / "system.md").write_text("# System\nProjects index.", encoding="utf-8")
        result = _load_context(str(tmp_path))
        assert "me.md" in result
        assert "Nelson, developer." in result
        assert "system.md" in result
        assert "Projects index." in result

    def test_missing_file_skipped_gracefully(self, tmp_path):
        (tmp_path / "me.md").write_text("# Me", encoding="utf-8")
        # system.md intentionally missing
        result = _load_context(str(tmp_path))
        assert "me.md" in result
        assert "system.md" not in result

    def test_both_missing_returns_empty(self, tmp_path):
        result = _load_context(str(tmp_path))
        assert result == ""


class TestAnalyseTweet:
    def _make_tweet(self):
        return TweetData(
            url="https://x.com/user/status/123",
            tweet_id="123",
            username="user",
            author_name="User",
            text="Claude Code is a system, not just an assistant.",
        )

    def _make_groq_response(self, title="Test Title", takeaways=None, tags=None):
        if takeaways is None:
            takeaways = [
                "Takeaway 1",
                "Takeaway 2",
                "Takeaway 3",
                "Takeaway 4",
                "[Challenge] Question your approach",
            ]
        if tags is None:
            tags = ["ai", "productivity"]
        mock = MagicMock()
        mock.choices[0].message.content = json.dumps(
            {"title": title, "takeaways": takeaways, "tags": tags}
        )
        return mock

    @patch("xread.analyser.Groq")
    def test_analyse_returns_insight(self, mock_groq_cls, tmp_path):
        (tmp_path / "me.md").write_text("# Me", encoding="utf-8")
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_groq_response()

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            result = analyse_tweet(self._make_tweet(), vault_path=str(tmp_path))

        assert isinstance(result, ReadInsight)
        assert result.title == "Test Title"
        assert len(result.takeaways) == 5
        assert len(result.tags) == 2

    @patch("xread.analyser.Groq")
    def test_raises_on_invalid_json(self, mock_groq_cls, tmp_path):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json at all"))]
        )

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with pytest.raises(RuntimeError, match="invalid JSON"):
                analyse_tweet(self._make_tweet(), vault_path=str(tmp_path))

    @patch("xread.analyser.Groq")
    def test_raises_on_wrong_takeaway_count(self, mock_groq_cls, tmp_path):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_groq_response(
            takeaways=["only one"]
        )

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with pytest.raises(RuntimeError, match="Expected 5 takeaways"):
                analyse_tweet(self._make_tweet(), vault_path=str(tmp_path))

    @patch("xread.analyser.Groq")
    def test_raises_on_empty_title(self, mock_groq_cls, tmp_path):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_groq_response(title="")

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with pytest.raises(RuntimeError, match="empty title"):
                analyse_tweet(self._make_tweet(), vault_path=str(tmp_path))
