"""
tests/test_style.py
Tests for Style & Quality Agent.
LLM calls are mocked - no OpenAI API needed.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from agents.style_quality_agent import build_prompt, parse_llm_response, run
from utils.pipeline_state import (
    PipelineState, ParsedDiff, FileDiff, SecurityFindings, SecurityFinding
)


# ── Sample Data ────────────────────────────────────────────────

SAMPLE_FILE = FileDiff(
    filename="auth.py",
    language="python",
    additions=5,
    deletions=2,
    patch="+def authenticate(username, password):\n+    return check_hash(username, password)"
)

SAMPLE_DIFF = ParsedDiff(
    files=[SAMPLE_FILE],
    total_additions=5,
    total_deletions=2,
    summary="1 file changed"
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

GOOD_SCORE_RESPONSE = json.dumps({
    "readability_score": 9.0,
    "naming_score": 8.5,
    "complexity_score": 8.0,
    "best_practices_score": 9.0,
    "overall_score": 8.6,
    "strengths": ["Clear function name", "Single responsibility"],
    "improvements": ["Add docstring", "Add type hints"]
})

LOW_SCORE_RESPONSE = json.dumps({
    "readability_score": 4.0,
    "naming_score": 3.5,
    "complexity_score": 4.0,
    "best_practices_score": 3.0,
    "overall_score": 3.6,
    "strengths": ["Code runs"],
    "improvements": ["Rename variables", "Reduce nesting", "Add comments"]
})


# ── build_prompt ───────────────────────────────────────────────

def test_build_prompt_includes_filename():
    """Prompt includes filename."""
    prompt = build_prompt(SAMPLE_DIFF)
    assert "auth.py" in prompt

def test_build_prompt_includes_patch():
    """Prompt includes code patch."""
    prompt = build_prompt(SAMPLE_DIFF)
    assert "authenticate" in prompt

def test_build_prompt_includes_security_context():
    """Prompt includes security findings as context."""
    prompt = build_prompt(SAMPLE_DIFF, CRITICAL_SECURITY)
    assert "SQL Injection" in prompt
    assert "Security context" in prompt

def test_build_prompt_no_security_context():
    """Prompt works without security findings."""
    prompt = build_prompt(SAMPLE_DIFF, None)
    assert "auth.py" in prompt
    assert "Security context" not in prompt


# ── parse_llm_response ─────────────────────────────────────────

def test_parse_good_score():
    """Parses high quality scores correctly."""
    result = parse_llm_response(GOOD_SCORE_RESPONSE)
    assert result.overall_score == 8.6
    assert result.readability_score == 9.0

def test_parse_low_score():
    """Parses low quality scores correctly."""
    result = parse_llm_response(LOW_SCORE_RESPONSE)
    assert result.overall_score == 3.6
    assert len(result.improvements) == 3

def test_parse_calculates_overall_if_missing():
    """Calculates overall_score if not in response."""
    response = json.dumps({
        "readability_score": 8.0,
        "naming_score": 8.0,
        "complexity_score": 8.0,
        "best_practices_score": 8.0,
        "strengths": ["Good"],
        "improvements": []
    })
    result = parse_llm_response(response)
    assert result.overall_score == 8.0

def test_parse_strips_markdown():
    """Parser handles markdown-wrapped JSON."""
    wrapped = f"```json\n{GOOD_SCORE_RESPONSE}\n```"
    result = parse_llm_response(wrapped)
    assert result.overall_score == 8.6

def test_parse_strengths_and_improvements():
    """Strengths and improvements lists are populated."""
    result = parse_llm_response(GOOD_SCORE_RESPONSE)
    assert len(result.strengths) == 2
    assert len(result.improvements) == 2


# ── run() ──────────────────────────────────────────────────────

def make_mock_response(content: str):
    mock = MagicMock()
    mock.choices[0].message.content = content
    return mock

def test_run_skips_when_skip_style_true():
    """run() skips analysis when skip_style=True."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.skip_style = True
    result = run(state)
    assert result.quality_score is None
    assert result.current_step == "summary"

def test_run_no_parsed_diff_adds_error():
    """run() handles missing parsed_diff gracefully."""
    state = PipelineState(raw_input="test")
    result = run(state)
    assert len(result.errors) > 0
    assert result.quality_score is None

def test_run_populates_quality_score():
    """run() fills state.quality_score correctly."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF
    state.security_findings = CLEAN_SECURITY

    with patch("agents.style_quality_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(GOOD_SCORE_RESPONSE)
        result = run(state)

    assert result.quality_score is not None
    assert result.quality_score.overall_score == 8.6

def test_run_advances_current_step():
    """run() sets current_step to 'summary'."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF

    with patch("agents.style_quality_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.return_value = \
            make_mock_response(GOOD_SCORE_RESPONSE)
        result = run(state)

    assert result.current_step == "summary"

def test_run_handles_exception_gracefully():
    """run() catches exceptions and logs to errors."""
    state = PipelineState(raw_input="test")
    state.parsed_diff = SAMPLE_DIFF

    with patch("agents.style_quality_agent.OpenAI") as MockOpenAI:
        MockOpenAI.return_value.chat.completions.create.side_effect = \
            Exception("API timeout")
        result = run(state)

    assert len(result.errors) > 0
    assert "StyleQualityAgent error" in result.errors[0]