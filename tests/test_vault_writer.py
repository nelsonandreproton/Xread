"""Tests for xread.vault_writer module."""

import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from xread.fetcher import TweetData
from xread.analyser import ReadInsight
from xread.vault_writer import write_to_vault, _slugify, _render_note


class TestSlugify:
    def test_basic(self):
        assert _slugify("Claude Code as a System") == "claude-code-as-a-system"

    def test_special_chars_removed(self):
        assert _slugify("Hello, World! #AI") == "hello-world-ai"

    def test_long_title_truncated(self):
        long = "a" * 100
        assert len(_slugify(long)) <= 60

    def test_multiple_spaces_collapsed(self):
        assert _slugify("too   many   spaces") == "too-many-spaces"


class TestRenderNote:
    def _make_tweet(self):
        return TweetData(
            url="https://x.com/user/status/123",
            tweet_id="123",
            username="user",
            author_name="User",
            text="Some tweet text",
        )

    def _make_insight(self):
        return ReadInsight(
            title="Test Title",
            takeaways=["T1", "T2", "T3", "T4", "[Challenge] T5"],
            tags=["ai", "productivity"],
        )

    def test_note_contains_source_url(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        assert "https://x.com/user/status/123" in note

    def test_note_contains_author(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        assert "@user" in note

    def test_note_contains_title(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        assert "# Test Title" in note

    def test_note_contains_all_takeaways(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        for t in ["T1", "T2", "T3", "T4", "[Challenge] T5"]:
            assert t in note

    def test_note_contains_tags(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        assert '"ai"' in note
        assert '"productivity"' in note

    def test_note_contains_date(self):
        note = _render_note(self._make_tweet(), self._make_insight(), "2026-03-27")
        assert "2026-03-27" in note


class TestWriteToVault:
    def _make_tweet(self):
        return TweetData(
            url="https://x.com/user/status/123",
            tweet_id="123",
            username="user",
            author_name="User",
            text="Tweet text",
        )

    def _make_insight(self):
        return ReadInsight(
            title="My Insight Title",
            takeaways=["T1", "T2", "T3", "T4", "[Challenge] T5"],
            tags=["ai"],
        )

    @patch("xread.vault_writer._git")
    def test_creates_reads_directory(self, mock_git, tmp_path):
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            write_to_vault(self._make_tweet(), self._make_insight(), vault_path=str(tmp_path))
        assert (tmp_path / "reads").is_dir()

    @patch("xread.vault_writer._git")
    def test_creates_note_file(self, mock_git, tmp_path):
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            filename = write_to_vault(
                self._make_tweet(), self._make_insight(), vault_path=str(tmp_path)
            )
        note_path = tmp_path / "reads" / filename
        assert note_path.exists()
        content = note_path.read_text(encoding="utf-8")
        assert "My Insight Title" in content

    @patch("xread.vault_writer._git")
    def test_filename_contains_date_and_slug(self, mock_git, tmp_path):
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            filename = write_to_vault(
                self._make_tweet(), self._make_insight(), vault_path=str(tmp_path)
            )
        assert "my-insight-title" in filename
        assert filename.endswith(".md")
        # Date prefix: YYYY-MM-DD
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}-", filename)

    @patch("xread.vault_writer._git")
    def test_git_add_commit_push_called(self, mock_git, tmp_path):
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            filename = write_to_vault(
                self._make_tweet(), self._make_insight(), vault_path=str(tmp_path)
            )
        calls = [str(c) for c in mock_git.call_args_list]
        assert any("add" in c for c in calls)
        assert any("commit" in c for c in calls)
        assert any("push" in c for c in calls)
