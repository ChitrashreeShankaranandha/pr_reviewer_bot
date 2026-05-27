"""
agents/summary_agent.py
Aggregates all agent findings into a final structured review summary.
Populates: state.review_summary
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from utils.pipeline_state import (
    PipelineState, SecurityFindings, QualityScore, ReviewSummary
)

load_dotenv()

# ── Summary System Prompt ──────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = """You are a senior engineering lead writing a final code review summary.

You will be given:
- Security findings from a security review agent
- Quality scores from a style review agent
- Information about the files changed

Your job is to synthesize all of this into a clear, actionable review summary.

Return ONLY a valid JSON object in this exact format, no markdown, no extra text:
{
  "summary": "2-3 sentence overall assessment of the PR",
  "security_highlights": [
    "Key security finding 1",
    "Key security finding 2"
  ],
  "quality_highlights": [
    "Key quality observation 1",
    "Key quality observation 2"
  ],
  "action_items": [
    "Specific action the developer must take 1",
    "Specific action the developer must take 2"
  ]
}

Be specific and actionable. Reference actual filenames and issues found.
If no issues were found in a category, say so positively."""


# ── Verdict Logic ──────────────────────────────────────────────

def determine_verdict(
    security_findings: SecurityFindings = None,
    quality_score: QualityScore = None,
    llm_security_report=None
) -> str:
    """
    Determine PR verdict using deterministic rules.
    No LLM needed — clear-cut logic is faster and more reliable.
    """
    # Critical or high security = always reject
    if security_findings and not security_findings.passed:
        return "rejected"

    # Poor quality score = needs changes
    if quality_score and quality_score.overall_score < 5.0:
        return "needs_changes"

    # Security passed but has medium/low findings = needs changes
    if security_findings and len(security_findings.findings) > 0:
        return "needs_changes"

    # Quality is decent but not great
    if quality_score and quality_score.overall_score < 7.5:
        return "needs_changes"
    
    # Blocked by LLM Security Guard = always reject
    if llm_security_report and llm_security_report.blocked:
        return "rejected"

    # Critical or high security = always reject
    if security_findings and not security_findings.passed:
        return "rejected"

    return "approved"


# ── Prompt Builder ─────────────────────────────────────────────

def build_prompt(state: PipelineState) -> str:
    """Assemble full context from all agents for the summary prompt."""
    parts = []

    # PR metadata
    if state.pr_metadata:
        m = state.pr_metadata
        parts.append(f"PR: #{m.pr_number} — {m.title}")
        parts.append(f"Author: {m.author} | {m.base_branch} ← {m.head_branch}")
        parts.append(f"Files changed: {m.files_changed}")
        parts.append("")

    # Files changed
    if state.parsed_diff:
        parts.append("Files reviewed:")
        for f in state.parsed_diff.files:
            parts.append(
                f"  - {f.filename} ({f.language}): "
                f"+{f.additions} additions, -{f.deletions} deletions"
            )
        parts.append("")

    # Security findings
    if state.security_findings:
        sf = state.security_findings
        parts.append(f"Security Review: overall_risk={sf.overall_risk}, passed={sf.passed}")
        if sf.findings:
            parts.append("Security findings:")
            for f in sf.findings:
                parts.append(
                    f"  - [{f.severity.upper()}] {f.category} in {f.filename}: "
                    f"{f.description}"
                )
        else:
            parts.append("No security issues found.")
        parts.append("")

    # Quality scores
    if state.quality_score:
        q = state.quality_score
        parts.append(f"Quality Review: overall={q.overall_score}/10")
        parts.append(f"  Readability: {q.readability_score}/10")
        parts.append(f"  Naming: {q.naming_score}/10")
        parts.append(f"  Complexity: {q.complexity_score}/10")
        parts.append(f"  Best Practices: {q.best_practices_score}/10")
        if q.strengths:
            parts.append(f"  Strengths: {', '.join(q.strengths)}")
        if q.improvements:
            parts.append(f"  Improvements: {', '.join(q.improvements)}")
        parts.append("")

    # LLM Security Guard block note
    if state.llm_security_report and state.llm_security_report.blocked:
        parts.append(f"IMPORTANT: Pipeline was blocked by LLM Security Guard.")
        parts.append(f"Reason: Malicious content detected in diff ({state.llm_security_report.risk_level} risk).")
        parts.append(f"Threats found: {len(state.llm_security_report.threats)}")
        for t in state.llm_security_report.threats:
            parts.append(f"  - [{t.severity.upper()}] {t.threat_type}: {t.evidence[:100]}")

    # Skip style note
    if state.skip_style:
        parts.append("Note: Style review was skipped due to critical security findings.")

    return "\n".join(parts)


# ── Response Parser ────────────────────────────────────────────

def parse_llm_response(response: str) -> dict:
    """Parse GPT JSON response into a dict."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    return json.loads(cleaned)


# ── Agent Entrypoint ───────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """Main Summary Agent entrypoint."""
    print("[SummaryAgent] Starting...")

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = build_prompt(state)
        print("[SummaryAgent] Generating final review summary...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Summarize this review:\n\n{prompt}"}
            ]
        )

        raw_response = response.choices[0].message.content
        data = parse_llm_response(raw_response)

        # Determine verdict with deterministic logic
        verdict = determine_verdict(
            state.security_findings,
            state.quality_score,
            state.llm_security_report
        )

        state.review_summary = ReviewSummary(
            verdict=verdict,
            summary=data.get("summary", "Review complete."),
            security_highlights=data.get("security_highlights", []),
            quality_highlights=data.get("quality_highlights", []),
            action_items=data.get("action_items", [])
        )

        state.current_step = "complete"
        print(f"[SummaryAgent] Verdict: {verdict.upper()}")
        print("[SummaryAgent] Done.")

    except Exception as e:
        error_msg = f"SummaryAgent error: {str(e)}"
        print(f"[SummaryAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state