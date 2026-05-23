"""
tests/test_security.py
Tests for Security Review Agent.
LLM calls are mocked - no OpenAI API needed for tests.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from agents.security_review_agent import build_prompt, parse_llm_response, run
from utils.pipeline_state import PipelineState, ParsedDiff, FileDiff


# ── Sample Data ────────────────────────────────────────────────

SAFE_FILE = FileDiff(
    filename="utils.py",
    language="python",
    additions=3,
    deletions=1,
    patch="+def helper():\n+    return True"
)

VULNERABLE_FILE = FileDiff(
    filename="db.py",
    language="python",
    additions=2,
    deletions=1,
    patch='+query = f"SELECT * FROM users WHERE id={user_id}"\n+password = "admin123"'
)

SAFE_DIFF = ParsedDiff(
    files=[SAFE_FILE],
    total_additions=3,
    total_deletions=1,
    summary="1 file changed"
)

VULNERABLE_DIFF = ParsedDiff(
    files=[VULNERABLE_FILE],
    total_additions=2,
    total_deletions=1,
    summary="1 file changed"
)

CLEAN_RESPONSE = json.dumps({
    "findings": [],
    "overall_risk": "none",
    "summary": "No security issues detected"
})

CRITICAL_RESPONSE = json.dumps({
    "findings": [
        {
            "filename": "db.py",
            "line": "+query = f\"SELECT...",
            "severity": "critical",
            "category": "SQL Injection",
            "description": "Unsanitized f-string used in SQL query",
            "recommendation": "Use parameterized queries"
        },
        {
            "filename": "db.py",
            "line": '+password = "admin123"',
            "severity": "high",
            "category": "Broken Authentication",
            "description": "Hardcoded password found",
            "recommendation": "Use environment variables"
        }
    ],
    "overall_risk": "critical",
    "summary": "2 critical security issues found"
})


# ── build_prompt ───────────────────────────────────────────────

def test_build_prompt_includes_filename():
    """Prompt includes the filename."""
    prompt = build_prompt(SAFE_DIFF)
    assert "utils.py" in prompt

def test_build_prompt_includes_language():
    """Prompt includes the language."""
    prompt = build_prompt(SAFE_DIFF)
    assert "python" in prompt

def test_build_prompt_includes_patch():
    """Prompt includes the actual code patch."""
    prompt = build_prompt(VULNERABLE_DIFF)
    assert "admin123" in prompt


# ── parse_llm_response ─────────────────────────────────────────

def test_parse_clean_response_no_findings():
    """Clean response returns empty findings and passed=True."""
    result = parse_llm_response(CLEAN_RESPONSE)
    assert result.findings == []
    assert result.overall_risk == "none"
    assert result.passed == True

def test_parse_critical_response_findings():
    """Critical response returns findings list."""
    result = parse_llm_response(CRITICAL_RESPONSE)
    assert len(result.findings) == 2

def test_parse_critical_response_passed_false():
    """Critical findings set passed=False."""
    result = parse_llm_response(CRITICAL_RESPONSE)
    assert result.passed == False

def test_parse_critical_response_severity():
    """First finding has correct severity."""
    result = parse_llm_response(CRITICAL_RESPONSE)
    severities = [f.severity for f in result.findings]
    assert "critical" in severities

def test_parse_response_strips_markdown():
    """Parser handles markdown-wrapped JSON."""
    wrapped = f"```json\n{CLEAN_RESPONSE}\n```"
    result = parse_llm_response(wrapped)
    assert result.passed == True

def test_parse_high_severity_sets_passed_false():
    """High severity alone sets passed=False."""
    response = json.dumps({
        "findings": [{
            "filename": "auth.py",
            "severity": "high",
            "category": "Broken Auth",
            "description": "Weak token",
            "recommendation": "Use JWT"
        }],
        "overall_risk": "high",
        "summary": "1 high issue"
    })
    result = parse_llm_response(response)
    assert result.passed == False

def test_parse_medium_severity_passed_true():
    """Medium severity alone keeps passed=True."""
    response = json.dumps({
        "findings": [{
            "filename": "app.py",
            "severity": "medium",
            "category": "Misconfiguration",
            "description": "Debug mode on",
            "recommendation": "Disable in production"
        }],
        "overall_risk": "medium",
        "summary": "1 medium issue"
    })
    result = parse_llm_response(response)
    assert result.passed == True


# ── run() with mocked LLM ──────────────────────────────────────

def make_mock_response(content: str):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response

def test_run_no_parsed_diff_adds_error():
    """run() handles missing parsed_diff gracefully."""
    state = PipelineState(raw_input="test")
    result = run(state)
    assert len(result.errors) > 0
    assert result.security_findings is None

def test_run_clean_diff_passed():
    """run() with clean diff sets passed=True."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAFE_DIFF

    with patch("agents.security_review_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(CLEAN_RESPONSE)
        result = run(state)

    assert result.security_findings is not None
    assert result.security_findings.passed == True
    assert result.skip_style == False

def test_run_vulnerable_diff_skip_style():
    """run() with critical findings sets skip_style=True."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = VULNERABLE_DIFF

    with patch("agents.security_review_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(CRITICAL_RESPONSE)
        result = run(state)

    assert result.security_findings.passed == False
    assert result.skip_style == True

def test_run_advances_current_step():
    """run() sets current_step to 'style'."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAFE_DIFF

    with patch("agents.security_review_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(CLEAN_RESPONSE)
        result = run(state)

    assert result.current_step == "style"

def test_run_handles_exception_gracefully():
    """run() catches exceptions and appends to errors."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAFE_DIFF

    with patch("agents.security_review_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.side_effect = \
            Exception("API timeout")
        result = run(state)

    assert len(result.errors) > 0
    assert "SecurityReviewAgent error" in result.errors[0]