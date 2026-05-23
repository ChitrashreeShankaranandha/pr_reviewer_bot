"""
agents/style_quality_agent.py
Reviews code quality: readability, naming, complexity, best practices.
Populates: state.quality_score
Skips if state.skip_style is True (critical security issues found upstream)
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from utils.pipeline_state import (
    PipelineState, ParsedDiff, SecurityFindings, QualityScore
)

load_dotenv()

# ── Style System Prompt ────────────────────────────────────────

STYLE_SYSTEM_PROMPT = """You are a senior software engineer conducting a code quality review.

Analyze the provided code diff and score it on these four dimensions (0.0 to 10.0 each):

- readability_score: Is the code easy to read and understand at a glance?
- naming_score: Are variables, functions, and classes named clearly and consistently?
- complexity_score: Are functions concise? Is nesting minimal? Is logic straightforward?
- best_practices_score: Does it follow language conventions? Are there code smells or anti-patterns?

Also provide:
- overall_score: Your holistic assessment (0.0 to 10.0)
- strengths: 2-3 specific things done well
- improvements: 1-3 specific, actionable suggestions

Return ONLY a valid JSON object in this exact format, no markdown, no extra text:
{
  "readability_score": 8.5,
  "naming_score": 9.0,
  "complexity_score": 7.0,
  "best_practices_score": 8.0,
  "overall_score": 8.1,
  "strengths": [
    "Clear and descriptive function names",
    "Good use of early returns"
  ],
  "improvements": [
    "Function login() is doing too many things - consider splitting",
    "Add docstrings to public functions"
  ]
}"""


# ── Prompt Builder ─────────────────────────────────────────────

def build_prompt(parsed_diff: ParsedDiff,
                 security_findings: SecurityFindings = None) -> str:
    """Format diff and optional security context for the LLM."""
    parts = []

    # Add security context if available
    if security_findings and security_findings.findings:
        parts.append("Security context (already flagged, focus on style):")
        for f in security_findings.findings:
            parts.append(f"  - [{f.severity}] {f.category} in {f.filename}")
        parts.append("")

    # Add each file's diff
    for file in parsed_diff.files:
        parts.append(f"File: {file.filename} ({file.language})")
        parts.append(f"Changes: +{file.additions} additions, -{file.deletions} deletions")
        parts.append("Patch:")
        parts.append(file.patch)
        parts.append("")

    return "\n".join(parts)


# ── Response Parser ────────────────────────────────────────────

def parse_llm_response(response: str) -> QualityScore:
    """Parse GPT JSON response into QualityScore model."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Calculate overall if not provided
    if "overall_score" not in data:
        scores = [
            data.get("readability_score", 5.0),
            data.get("naming_score", 5.0),
            data.get("complexity_score", 5.0),
            data.get("best_practices_score", 5.0),
        ]
        data["overall_score"] = round(sum(scores) / len(scores), 2)

    return QualityScore(
        readability_score=data.get("readability_score", 5.0),
        naming_score=data.get("naming_score", 5.0),
        complexity_score=data.get("complexity_score", 5.0),
        best_practices_score=data.get("best_practices_score", 5.0),
        overall_score=data.get("overall_score", 5.0),
        strengths=data.get("strengths", []),
        improvements=data.get("improvements", [])
    )


# ── Agent Entrypoint ───────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """Main Style & Quality Agent entrypoint."""
    print("[StyleQualityAgent] Starting...")

    # Skip if critical security issues were found upstream
    if state.skip_style:
        print("[StyleQualityAgent] Skipping — critical security issues found.")
        state.current_step = "summary"
        return state

    if not state.parsed_diff:
        error_msg = "StyleQualityAgent: No parsed diff available."
        print(f"[StyleQualityAgent] ERROR: {error_msg}")
        state.errors.append(error_msg)
        return state

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = build_prompt(state.parsed_diff, state.security_findings)
        print(f"[StyleQualityAgent] Reviewing {len(state.parsed_diff.files)} files...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": STYLE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Review this code diff:\n\n{prompt}"}
            ]
        )

        raw_response = response.choices[0].message.content
        state.quality_score = parse_llm_response(raw_response)

        state.current_step = "summary"
        print(f"[StyleQualityAgent] Overall score: {state.quality_score.overall_score}/10")
        print("[StyleQualityAgent] Done.")

    except Exception as e:
        error_msg = f"StyleQualityAgent error: {str(e)}"
        print(f"[StyleQualityAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state