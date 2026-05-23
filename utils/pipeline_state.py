"""
utils/pipeline_state.py
Shared Pydantic models passed between all agents via LangGraph.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


# ── Input ─────────────────────────────────────────────────────

class PRMetadata(BaseModel):
    pr_url: str
    repo_name: str
    pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    files_changed: int


# ── Code Parser Output ─────────────────────────────────────────

class FileDiff(BaseModel):
    filename: str
    language: str
    additions: int
    deletions: int
    patch: str  # raw diff patch


class ParsedDiff(BaseModel):
    files: list[FileDiff]
    total_additions: int
    total_deletions: int
    summary: str  # brief description of what changed


# ── Security Agent Output ──────────────────────────────────────

class SecurityFinding(BaseModel):
    filename: str
    line: Optional[str] = None
    severity: Literal["critical", "high", "medium", "low"]
    category: str   # e.g. "SQL Injection", "Hardcoded Secret"
    description: str
    recommendation: str


class SecurityFindings(BaseModel):
    findings: list[SecurityFinding]
    overall_risk: Literal["critical", "high", "medium", "low", "none"]
    passed: bool  # True if no critical/high findings


# ── Style & Quality Agent Output ───────────────────────────────

class QualityScore(BaseModel):
    readability_score: float = Field(ge=0, le=10)
    naming_score: float = Field(ge=0, le=10)
    complexity_score: float = Field(ge=0, le=10)
    best_practices_score: float = Field(ge=0, le=10)
    overall_score: float = Field(ge=0, le=10)
    strengths: list[str]
    improvements: list[str]


# ── Summary Agent Output ───────────────────────────────────────

class ReviewSummary(BaseModel):
    verdict: Literal["approved", "needs_changes", "rejected"]
    summary: str
    security_highlights: list[str]
    quality_highlights: list[str]
    action_items: list[str]
    post_to_github: bool = False


# ── Master Pipeline State ──────────────────────────────────────

class PipelineState(BaseModel):
    # Input
    raw_input: str                          # PR URL or pasted diff
    use_github: bool = False                # True = fetch from GitHub API

    # Agent outputs (populated as pipeline runs)
    pr_metadata: Optional[PRMetadata] = None
    raw_diff: Optional[str] = None
    parsed_diff: Optional[ParsedDiff] = None
    security_findings: Optional[SecurityFindings] = None
    quality_score: Optional[QualityScore] = None
    review_summary: Optional[ReviewSummary] = None

    # Pipeline control
    current_step: str = "fetcher"
    skip_style: bool = False  # set True by router if critical security issue
    errors: list[str] = []