"""
tests/test_fetcher.py
Tests for Code Fetcher Agent.
Uses pasted diff mode (no GitHub API needed for tests).
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.code_fetcher_agent import parse_pr_url, fetch_from_paste, run
from utils.pipeline_state import PipelineState


SAMPLE_DIFF = """--- auth.py
+++ auth.py
@@ -1,5 +1,8 @@
+import hashlib
+
 def login(username, password):
-    if password == "admin123":
+    hashed = hashlib.sha256(password.encode()).hexdigest()
+    if hashed == get_stored_hash(username):
         return True
     return False"""


# ── parse_pr_url ───────────────────────────────────────────────

def test_parse_pr_url_valid():
    """Correctly extracts repo name and PR number from URL."""
    repo, number = parse_pr_url("https://github.com/owner/repo/pull/42")
    assert repo == "owner/repo"
    assert number == 42


def test_parse_pr_url_invalid():
    """Raises ValueError for non-PR URLs."""
    with pytest.raises(ValueError):
        parse_pr_url("https://github.com/owner/repo")


def test_parse_pr_url_different_numbers():
    """Handles different PR numbers correctly."""
    _, number = parse_pr_url("https://github.com/org/project/pull/999")
    assert number == 999


# ── fetch_from_paste ───────────────────────────────────────────

def test_fetch_from_paste_returns_diff():
    """Returns None metadata and the raw diff text."""
    metadata, diff = fetch_from_paste(SAMPLE_DIFF)
    assert metadata is None
    assert diff == SAMPLE_DIFF


def test_fetch_from_paste_preserves_content():
    """Diff content is not modified."""
    _, diff = fetch_from_paste(SAMPLE_DIFF)
    assert "hashlib" in diff
    assert "admin123" in diff


# ── run() with pasted diff ─────────────────────────────────────

def test_run_pasted_diff_populates_state():
    """run() populates raw_diff and advances current_step."""
    state = PipelineState(raw_input=SAMPLE_DIFF, use_github=False)
    result = run(state)
    assert result.raw_diff == SAMPLE_DIFF
    assert result.current_step == "parser"
    assert result.errors == []


def test_run_pasted_diff_no_metadata():
    """run() with pasted diff leaves pr_metadata as None."""
    state = PipelineState(raw_input=SAMPLE_DIFF, use_github=False)
    result = run(state)
    assert result.pr_metadata is None


# ── run() with GitHub mode (mocked) ───────────────────────────

def test_run_github_mode_mocked():
    """run() with use_github=True fetches metadata (GitHub API mocked)."""
    mock_file = MagicMock()
    mock_file.filename = "auth.py"
    mock_file.patch = "+new code"

    mock_pr = MagicMock()
    mock_pr.title = "Fix auth bug"
    mock_pr.user.login = "devuser"
    mock_pr.base.ref = "main"
    mock_pr.head.ref = "fix/auth"
    mock_pr.changed_files = 1
    mock_pr.get_files.return_value = [mock_file]

    mock_repo = MagicMock()
    mock_repo.get_pull.return_value = mock_pr

    with patch("agents.code_fetcher_agent.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo

        state = PipelineState(
            raw_input="https://github.com/owner/repo/pull/1",
            use_github=True
        )
        result = run(state)

    assert result.pr_metadata is not None
    assert result.pr_metadata.title == "Fix auth bug"
    assert result.pr_metadata.author == "devuser"
    assert result.raw_diff is not None
    assert result.errors == []


# ── Error handling ─────────────────────────────────────────────

def test_run_handles_error_gracefully():
    """run() catches exceptions and appends to errors list."""
    state = PipelineState(
        raw_input="https://github.com/owner/repo/pull/1",
        use_github=True  # will fail - no real token in test
    )
    with patch("agents.code_fetcher_agent.Github") as MockGithub:
        MockGithub.side_effect = Exception("API connection failed")
        result = run(state)

    assert len(result.errors) > 0
    assert "CodeFetcherAgent error" in result.errors[0]