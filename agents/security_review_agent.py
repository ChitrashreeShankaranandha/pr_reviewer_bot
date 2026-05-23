"""
agents/security_review_agent.py
Reviews parsed diff for security vulnerabilities using OWASP Top 10.
Populates: state.security_findings, state.skip_style
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from utils.pipeline_state import (
    PipelineState, ParsedDiff, SecurityFinding, SecurityFindings
)

load_dotenv()

# ── OWASP System Prompt ────────────────────────────────────────

OWASP_SYSTEM_PROMPT = """You are an expert security code reviewer specializing in OWASP Top 10 vulnerabilities.

Analyze the provided code diff and identify security issues including:
- A01 Injection: SQL injection, command injection, LDAP injection
- A02 Broken Authentication: hardcoded credentials, weak passwords, insecure tokens
- A03 Sensitive Data Exposure: API keys, secrets, passwords in code
- A05 Security Misconfiguration: debug mode, open CORS, default credentials
- A07 XSS: unescaped user input rendered to HTML
- A08 Insecure Deserialization: unsafe pickle, yaml.load without Loader
- A09 Vulnerable Components: use of known vulnerable functions

For each finding return severity as one of: critical, high, medium, low

Return ONLY a valid JSON object in this exact format, no markdown, no extra text:
{
  "findings": [
    {
      "filename": "auth.py",
      "line": "@@ -1,5 +1,8 @@",
      "severity": "critical",
      "category": "Broken Authentication",
      "description": "Hardcoded password found in login function",
      "recommendation": "Use environment variables and hashed password comparison"
    }
  ],
  "overall_risk": "critical",
  "summary": "1 critical issue found requiring immediate attention"
}

If no security issues are found, return:
{
  "findings": [],
  "overall_risk": "none",
  "summary": "No security issues detected"
}"""


# ── Prompt Builder ─────────────────────────────────────────────

def build_prompt(parsed_diff: ParsedDiff) -> str:
    """Format parsed diff into a readable prompt for the LLM."""
    parts = []
    for file in parsed_diff.files:
        parts.append(f"File: {file.filename} ({file.language})")
        parts.append(f"Changes: +{file.additions} additions, -{file.deletions} deletions")
        parts.append("Patch:")
        parts.append(file.patch)
        parts.append("")
    return "\n".join(parts)


# ── Response Parser ────────────────────────────────────────────

def parse_llm_response(response: str) -> SecurityFindings:
    """Parse GPT JSON response into SecurityFindings model."""

    # Strip markdown fences if present
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    findings = []
    for f in data.get("findings", []):
        findings.append(SecurityFinding(
            filename=f.get("filename", "unknown"),
            line=f.get("line"),
            severity=f.get("severity", "low"),
            category=f.get("category", "General"),
            description=f.get("description", ""),
            recommendation=f.get("recommendation", "")
        ))

    overall_risk = data.get("overall_risk", "none")

    # passed = True only if no critical or high findings
    passed = not any(
        f.severity in ("critical", "high") for f in findings
    )

    return SecurityFindings(
        findings=findings,
        overall_risk=overall_risk,
        passed=passed
    )


# ── Agent Entrypoint ───────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """Main Security Review Agent entrypoint."""
    print("[SecurityReviewAgent] Starting...")

    if not state.parsed_diff:
        error_msg = "SecurityReviewAgent: No parsed diff available."
        print(f"[SecurityReviewAgent] ERROR: {error_msg}")
        state.errors.append(error_msg)
        return state

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = build_prompt(state.parsed_diff)
        print(f"[SecurityReviewAgent] Analyzing {len(state.parsed_diff.files)} files...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": OWASP_SYSTEM_PROMPT},
                {"role": "user", "content": f"Review this code diff:\n\n{prompt}"}
            ]
        )

        raw_response = response.choices[0].message.content
        state.security_findings = parse_llm_response(raw_response)

        # If critical/high findings → skip style agent
        if not state.security_findings.passed:
            state.skip_style = True
            print(f"[SecurityReviewAgent] Risk: {state.security_findings.overall_risk} — flagging skip_style=True")
        else:
            print(f"[SecurityReviewAgent] Risk: {state.security_findings.overall_risk} — passed")

        state.current_step = "style"
        print("[SecurityReviewAgent] Done.")

    except Exception as e:
        error_msg = f"SecurityReviewAgent error: {str(e)}"
        print(f"[SecurityReviewAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state