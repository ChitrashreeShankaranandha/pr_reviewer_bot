"""
tests/test_pipeline_state.py
Tests for shared Pydantic models in PipelineState.
"""

import pytest
from utils.pipeline_state import (
    PipelineState, PRMetadata, FileDiff, ParsedDiff,
    SecurityFinding, SecurityFindings, QualityScore, ReviewSummary
)


# ── PipelineState ──────────────────────────────────────────────

def test_pipeline_state_defaults():
    """PipelineState initializes with correct defaults."""
    state = PipelineState(raw_input="https://github.com/test/repo/pull/1")
    assert state.current_step == "fetcher"
    assert state.skip_style == False
    assert state.errors == []
    assert state.pr_metadata is None
    assert state.raw_diff is None


def test_pipeline_state_accepts_input():
    """PipelineState stores raw_input correctly."""
    state = PipelineState(raw_input="some diff text", use_github=False)
    assert state.raw_input == "some diff text"
    assert state.use_github == False


# ── PRMetadata ─────────────────────────────────────────────────

def test_pr_metadata_creation():
    """PRMetadata stores all fields correctly."""
    meta = PRMetadata(
        pr_url="https://github.com/test/repo/pull/42",
        repo_name="test/repo",
        pr_number=42,
        title="Fix login bug",
        author="devuser",
        base_branch="main",
        head_branch="fix/login",
        files_changed=3
    )
    assert meta.pr_number == 42
    assert meta.author == "devuser"


# ── FileDiff & ParsedDiff ──────────────────────────────────────

def test_file_diff_creation():
    """FileDiff stores patch correctly."""
    diff = FileDiff(
        filename="auth.py",
        language="python",
        additions=10,
        deletions=2,
        patch="+ new line\n- old line"
    )
    assert diff.filename == "auth.py"
    assert diff.additions == 10


def test_parsed_diff_holds_multiple_files():
    """ParsedDiff holds a list of FileDiff objects."""
    files = [
        FileDiff(filename="a.py", language="python", additions=5, deletions=1, patch="+code"),
        FileDiff(filename="b.py", language="python", additions=3, deletions=0, patch="+more"),
    ]
    parsed = ParsedDiff(files=files, total_additions=8, total_deletions=1, summary="Added auth")
    assert len(parsed.files) == 2
    assert parsed.total_additions == 8


# ── SecurityFindings ───────────────────────────────────────────

def test_security_finding_severity_validation():
    """SecurityFinding only accepts valid severity levels."""
    finding = SecurityFinding(
        filename="db.py",
        severity="critical",
        category="SQL Injection",
        description="Unsanitized input passed to query",
        recommendation="Use parameterized queries"
    )
    assert finding.severity == "critical"


def test_security_finding_invalid_severity():
    """SecurityFinding rejects invalid severity values."""
    with pytest.raises(Exception):
        SecurityFinding(
            filename="db.py",
            severity="extreme",  # invalid
            category="Test",
            description="Test",
            recommendation="Test"
        )


def test_security_findings_passed_flag():
    """SecurityFindings.passed is True when no critical/high findings."""
    findings = SecurityFindings(
        findings=[],
        overall_risk="none",
        passed=True
    )
    assert findings.passed == True


# ── QualityScore ───────────────────────────────────────────────

def test_quality_score_range_validation():
    """QualityScore rejects scores outside 0-10."""
    with pytest.raises(Exception):
        QualityScore(
            readability_score=11,  # invalid - above 10
            naming_score=8,
            complexity_score=7,
            best_practices_score=9,
            overall_score=8,
            strengths=["Good naming"],
            improvements=["Reduce complexity"]
        )


def test_quality_score_valid():
    """QualityScore accepts valid scores."""
    score = QualityScore(
        readability_score=8.5,
        naming_score=9.0,
        complexity_score=7.0,
        best_practices_score=8.0,
        overall_score=8.1,
        strengths=["Clear variable names"],
        improvements=["Break up long functions"]
    )
    assert score.overall_score == 8.1


# ── ReviewSummary ──────────────────────────────────────────────

def test_review_summary_verdict_validation():
    """ReviewSummary only accepts valid verdict values."""
    with pytest.raises(Exception):
        ReviewSummary(
            verdict="maybe",  # invalid
            summary="Looks okay",
            security_highlights=[],
            quality_highlights=[],
            action_items=[]
        )


def test_review_summary_valid():
    """ReviewSummary stores verdict and action items correctly."""
    summary = ReviewSummary(
        verdict="needs_changes",
        summary="Found 2 security issues",
        security_highlights=["SQL injection in db.py"],
        quality_highlights=["Good naming conventions"],
        action_items=["Fix parameterized queries", "Add input validation"]
    )
    assert summary.verdict == "needs_changes"
    assert len(summary.action_items) == 2