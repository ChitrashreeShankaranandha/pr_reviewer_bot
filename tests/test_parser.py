"""
tests/test_parser.py
Tests for Code Parser Agent.
"""

import pytest
from agents.code_parser_agent import detect_language, parse_diff, summarize_diff, run
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

MULTI_FILE_DIFF = """--- auth.py
+++ auth.py
@@ -1,3 +1,4 @@
+import hashlib
 def login(user, pwd):
-    pass
+    return True
--- db.py
+++ db.py
@@ -1,3 +1,3 @@
 def query(sql):
-    return execute(sql)
+    return execute(sql, sanitized=True)"""


# ── detect_language ────────────────────────────────────────────

def test_detect_language_python():
    assert detect_language("auth.py") == "python"

def test_detect_language_javascript():
    assert detect_language("app.js") == "javascript"

def test_detect_language_typescript():
    assert detect_language("component.tsx") == "typescript"

def test_detect_language_unknown():
    assert detect_language("Makefile") == "unknown"

def test_detect_language_sql():
    assert detect_language("schema.sql") == "sql"


# ── parse_diff ─────────────────────────────────────────────────

def test_parse_diff_returns_file_list():
    """parse_diff returns a list of FileDiff objects."""
    files = parse_diff(SAMPLE_DIFF)
    assert len(files) == 1
    assert files[0].filename == "auth.py"

def test_parse_diff_detects_language():
    """parse_diff correctly detects Python."""
    files = parse_diff(SAMPLE_DIFF)
    assert files[0].language == "python"

def test_parse_diff_counts_additions():
    """parse_diff counts added lines correctly."""
    files = parse_diff(SAMPLE_DIFF)
    assert files[0].additions == 4

def test_parse_diff_counts_deletions():
    """parse_diff counts removed lines correctly."""
    files = parse_diff(SAMPLE_DIFF)
    assert files[0].deletions == 1

def test_parse_diff_multiple_files():
    """parse_diff handles multiple files in one diff."""
    files = parse_diff(MULTI_FILE_DIFF)
    assert len(files) == 2
    filenames = [f.filename for f in files]
    assert "auth.py" in filenames
    assert "db.py" in filenames

def test_parse_diff_empty_string():
    """parse_diff returns empty list for empty input."""
    files = parse_diff("")
    assert files == []

def test_parse_diff_preserves_patch():
    """parse_diff stores the patch content."""
    files = parse_diff(SAMPLE_DIFF)
    assert "admin123" in files[0].patch
    assert "hashlib" in files[0].patch


# ── summarize_diff ─────────────────────────────────────────────

def test_summarize_diff_single_file():
    """Summary mentions file count and filename."""
    files = parse_diff(SAMPLE_DIFF)
    summary = summarize_diff(files)
    assert "1 file changed" in summary
    assert "auth.py" in summary

def test_summarize_diff_multiple_files():
    """Summary correctly says 'files' plural."""
    files = parse_diff(MULTI_FILE_DIFF)
    summary = summarize_diff(files)
    assert "2 files changed" in summary

def test_summarize_diff_empty():
    """Summary handles empty file list."""
    assert summarize_diff([]) == "No files changed."


# ── run() ──────────────────────────────────────────────────────

def test_run_populates_parsed_diff():
    """run() fills state.parsed_diff correctly."""
    state = PipelineState(raw_input=SAMPLE_DIFF, use_github=False)
    state.raw_diff = SAMPLE_DIFF
    result = run(state)
    assert result.parsed_diff is not None
    assert len(result.parsed_diff.files) == 1

def test_run_advances_current_step():
    """run() sets current_step to 'security'."""
    state = PipelineState(raw_input=SAMPLE_DIFF, use_github=False)
    state.raw_diff = SAMPLE_DIFF
    result = run(state)
    assert result.current_step == "security"

def test_run_no_diff_adds_error():
    """run() handles missing raw_diff gracefully."""
    state = PipelineState(raw_input="", use_github=False)
    result = run(state)
    assert len(result.errors) > 0
    assert result.parsed_diff is None

def test_run_totals_are_correct():
    """run() calculates total additions and deletions."""
    state = PipelineState(raw_input=MULTI_FILE_DIFF, use_github=False)
    state.raw_diff = MULTI_FILE_DIFF
    result = run(state)
    assert result.parsed_diff.total_additions > 0
    assert result.parsed_diff.total_deletions > 0