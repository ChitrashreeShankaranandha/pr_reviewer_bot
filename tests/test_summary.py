"""
tests/test_summary.py
Tests for Summary Agent.
LLM calls are mocked - no OpenAI API needed.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from agents.summary_agent import build_prompt, determine_verdict, parse_llm_response, run
from utils.pipeline_state import (
    PipelineState, ParsedDiff, FileDiff, PRMetadata,
    SecurityFindings, SecurityFinding, QualityScore, ReviewSummary
)


# ── Sample Data ────────────────────────────────────────────────

SAMPLE_FILE = FileDiff(
    filename="auth.py",
    language="python",
    additions=5,
    deletions=2,
    patch="+def authenticate(user, pwd):\n+    return check_hash(user, pwd)"
)

SAMPLE_DIFF = ParsedDiff(
    files=[SAMPLE_FILE],
    total_additions=5,
    total_deletions=2,
    summary="1 file changed"
)

SAMPLE_METADATA = PRMetadata(
    pr_url="https://github.com/owner/repo/pull/42",
    repo_name="owner/repo",
    pr_number=42,
    title="Fix authentication logic",
    author="devuser",
    base_branch="main",
    head_branch="fix/auth",
    files_changed=1
)

CLEAN_SECURITY = SecurityFindings(
    findings=[],
    overall_risk="none",
    passed=True
)

CRITICAL_SECURITY = SecurityFindings(
    findings=[SecurityFinding(
        filename="auth.py",
        severity="critical",
        category="SQL Injection",
        description="Unsafe query",
        recommendation="Use parameterized queries"
    )],
    overall_risk="critical",
    passed=False
)

GOOD_QUALITY = QualityScore(
    readability_score=8.5,
    naming_score=9.0,
    complexity_score=8.0,
    best_practices_score=8.5,
    overall_score=8.5,
    strengths=["Clear naming", "Simple logic"],
    improvements=["Add docstrings"]
)

POOR_QUALITY = QualityScore(
    readability_score=3.0,
    naming_score=3.5,
    complexity_score=4.0,
    best_practices_score=3.0,
    overall_score=3.4,
    strengths=["Code runs"],
    improvements=["Rename variables", "Reduce nesting"]
)

SAMPLE_SUMMARY_RESPONSE = json.dumps({
    "summary": "This PR fixes authentication logic. Security looks clean and code quality is high.",
    "security_highlights": ["No security issues found"],
    "quality_highlights": ["Clear function naming", "Good use of helper functions"],
    "action_items": ["Add docstrings to public functions"]
})


# ── determine_verdict ──────────────────────────────────────────

def test_verdict_rejected_on_critical_security():
    """Critical security findings = rejected."""
    verdict = determine_verdict(CRITICAL_SECURITY, GOOD_QUALITY)
    assert verdict == "rejected"

def test_verdict_needs_changes_on_poor_quality():
    """Poor quality score = needs_changes."""
    verdict = determine_verdict(CLEAN_SECURITY, POOR_QUALITY)
    assert verdict == "needs_changes"

def test_verdict_approved_on_clean_diff():
    """Clean security and good quality = approved."""
    verdict = determine_verdict(CLEAN_SECURITY, GOOD_QUALITY)
    assert verdict == "approved"

def test_verdict_needs_changes_on_medium_findings():
    """Medium security findings = needs_changes."""
    medium_security = SecurityFindings(
        findings=[SecurityFinding(
            filename="app.py",
            severity="medium",
            category="Misconfiguration",
            description="Debug mode on",
            recommendation="Disable in production"
        )],
        overall_risk="medium",
        passed=True  # medium doesn't set passed=False
    )
    verdict = determine_verdict(medium_security, GOOD_QUALITY)
    assert verdict == "needs_changes"

def test_verdict_needs_changes_on_borderline_quality():
    """Quality score between 5-7.5 = needs_changes."""
    borderline = QualityScore(
        readability_score=7.0,
        naming_score=7.0,
        complexity_score=6.5,
        best_practices_score=7.0,
        overall_score=6.9,
        strengths=["Decent"],
        improvements=["Improve"]
    )
    verdict = determine_verdict(CLEAN_SECURITY, borderline)
    assert verdict == "needs_changes"

def test_verdict_no_inputs_returns_approved():
    """No findings and no quality score = approved."""
    verdict = determine_verdict(None, None)
    assert verdict == "approved"


# ── build_prompt ───────────────────────────────────────────────

def test_build_prompt_includes_security_findings():
    """Prompt includes security findings."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CRITICAL_SECURITY
    prompt = build_prompt(state)
    assert "SQL Injection" in prompt
    assert "critical" in prompt.lower()

def test_build_prompt_includes_quality_scores():
    """Prompt includes quality scores."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.quality_score = GOOD_QUALITY
    prompt = build_prompt(state)
    assert "8.5" in prompt
    assert "Quality Review" in prompt

def test_build_prompt_includes_pr_metadata():
    """Prompt includes PR metadata when available."""
    state = PipelineState(raw_input="test")
    state.pr_metadata = SAMPLE_METADATA
    state.parsed_diff = SAMPLE_DIFF
    prompt = build_prompt(state)
    assert "Fix authentication logic" in prompt
    assert "devuser" in prompt

def test_build_prompt_notes_skip_style():
    """Prompt mentions when style was skipped."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.skip_style = True
    prompt = build_prompt(state)
    assert "Style review was skipped" in prompt


# ── run() ──────────────────────────────────────────────────────

def make_mock_response(content: str):
    mock = MagicMock()
    mock.choices[0].message.content = content
    return mock

def test_run_populates_review_summary():
    """run() fills state.review_summary."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CLEAN_SECURITY
    state.quality_score = GOOD_QUALITY

    with patch("agents.summary_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(SAMPLE_SUMMARY_RESPONSE)
        result = run(state)

    assert result.review_summary is not None
    assert result.review_summary.verdict == "approved"

def test_run_verdict_rejected_on_critical():
    """run() returns rejected verdict for critical security."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CRITICAL_SECURITY
    state.quality_score = GOOD_QUALITY
    state.skip_style = True

    with patch("agents.summary_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(SAMPLE_SUMMARY_RESPONSE)
        result = run(state)

    assert result.review_summary.verdict == "rejected"

def test_run_advances_current_step():
    """run() sets current_step to 'complete'."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CLEAN_SECURITY

    with patch("agents.summary_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(SAMPLE_SUMMARY_RESPONSE)
        result = run(state)

    assert result.current_step == "complete"

def test_run_handles_exception_gracefully():
    """run() catches exceptions and logs to errors."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF

    with patch("agents.summary_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.side_effect = \
            Exception("API timeout")
        result = run(state)

    assert len(result.errors) > 0
    assert "SummaryAgent error" in result.errors[0]

def test_run_summary_has_action_items():
    """run() populates action items from LLM response."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CLEAN_SECURITY
    state.quality_score = GOOD_QUALITY

    with patch("agents.summary_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(SAMPLE_SUMMARY_RESPONSE)
        result = run(state)

    assert len(result.review_summary.action_items) > 0